import json
from datetime import UTC, datetime

import pytest
from sqlmodel import Session, select

from mes_core.enums import Role
from mes_server.config import Settings
from mes_server.db import create_db_engine, migrate
from mes_server.db.models import (
    AuditEntry,
    DowntimeEvent,
    ExecutionRecord,
    Product,
    Recipe,
    RecipeStep,
    Station,
    Unit,
    User,
    WorkOrder,
)
from mes_server.services import audit, backups, course_reset, downtime_reasons, products, users
from mes_server.services.backups import BackupError
from mes_server.services.course_reset import CONFIRMATION_WORD, ResetLevel
from mes_server.services.errors import InUseError, PermissionDeniedError, ValidationError


# ---------------------------------------------------------------------------------------------
# Fixtures: a migrated SQLite file with a full course of data
# ---------------------------------------------------------------------------------------------
@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mes.db').as_posix()}"
    migrate.upgrade(url)
    engine = create_db_engine(url)
    yield url, engine, tmp_path / "respaldos"
    engine.dispose()


def populate(engine):
    """A course's worth of data: catalogs, users and production history."""
    with Session(engine) as session:
        admin = users.create_user(
            session, username="admin", full_name="Admin", password="secret123", role=Role.ADMIN
        )
        student = users.create_user(
            session, username="alumno", full_name="Alumno", password="secret123", role=Role.OPERATOR
        )
        engineer = users.create_user(
            session,
            username="ing",
            full_name="Ing",
            password="secret123",
            role=Role.PROCESS_ENGINEER,
        )
        product = products.create_product(session, code="P-1", name="Producto")
        products.add_bom_item(session, product.id, component_code="C-1", quantity=1)
        station = Station(code="ST-10", name="Estación")
        session.add(station)
        session.flush()
        reason = downtime_reasons.create_reason(session, code="NO_MAT", description="Sin material")
        recipe = Recipe(product_id=product.id, name="Receta")
        step = RecipeStep(sequence=1, station_id=station.id, operation="OP", name="Paso")
        recipe.steps.append(step)
        order = WorkOrder(order_number="WO-1", product_id=product.id, quantity=1)
        session.add_all([recipe, order])
        session.flush()
        unit = Unit(serial_number="SN-1", work_order_id=order.id)
        session.add(unit)
        session.flush()
        now = datetime(2026, 11, 1, tzinfo=UTC)
        session.add(
            ExecutionRecord(
                unit_id=unit.id,
                recipe_step_id=step.id,
                station_id=station.id,
                operator_id=student.id,
                result="ok",
                started_at=now,
                finished_at=now,
            )
        )
        session.add(
            DowntimeEvent(
                station_id=station.id,
                reason_id=reason.id,
                reported_by_id=student.id,
                started_at=now,
            )
        )
        session.commit()
        return {"admin": admin.id, "student": student.id, "engineer": engineer.id}
    # fmt: skip


def count(engine, model):
    with Session(engine) as session:
        return len(session.exec(select(model)).all())


# ---------------------------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------------------------
def test_default_backup_dir_is_next_to_the_database(tmp_path):
    url = f"sqlite:///{(tmp_path / 'data' / 'mes.db').as_posix()}"
    assert backups.default_backup_dir(url) == tmp_path / "data" / "respaldos"


@pytest.mark.parametrize("url", ["sqlite://", "sqlite:///:memory:", "postgresql://u@h/db"])
def test_non_file_databases_have_no_backup_dir(url):
    assert backups.default_backup_dir(url) is None


def test_configured_backup_dir_wins(tmp_path):
    settings = Settings.from_env({"MES_BACKUP_DIR": str(tmp_path / "otros")})
    assert settings.resolve_backup_dir() == tmp_path / "otros"


def test_settings_default_backup_dir():
    assert str(Settings.from_env({}).resolve_backup_dir()) == "respaldos"


def test_backup_copies_the_database_and_writes_a_manifest(db):
    url, engine, backup_dir = db
    populate(engine)
    info = backups.create_backup(url, backup_dir, created_by="admin")

    assert info.path.is_file()
    assert info.file_name.startswith("mes-") and info.file_name.endswith(".db")
    assert info.schema_revision == migrate.head_revision()
    assert info.row_counts["products"] == 1
    assert info.row_counts["execution_records"] == 1
    manifest = json.loads(info.path.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifest["format"] == backups.MANIFEST_FORMAT
    assert manifest["created_by"] == "admin"
    assert manifest["reason"] == "manual"
    assert not list(backup_dir.glob("*.partial"))


def test_backup_is_a_working_database(db):
    url, engine, backup_dir = db
    populate(engine)
    info = backups.create_backup(url, backup_dir, created_by="admin")
    copy = create_db_engine(f"sqlite:///{info.path.as_posix()}")
    with Session(copy) as session:
        assert session.exec(select(Product)).one().code == "P-1"
    copy.dispose()


def test_backups_made_in_the_same_second_get_distinct_names(db):
    url, _, backup_dir = db
    first = backups.create_backup(url, backup_dir, created_by="a")
    second = backups.create_backup(url, backup_dir, created_by="a")
    assert first.file_name != second.file_name


def test_reason_is_part_of_the_file_name(db):
    url, _, backup_dir = db
    info = backups.create_backup(url, backup_dir, created_by="a", reason="Course Reset!")
    assert info.file_name.endswith("-course-reset.db")


def test_backup_requires_a_sqlite_file(tmp_path):
    with pytest.raises(BackupError):
        backups.create_backup("sqlite://", tmp_path, created_by="a")
    with pytest.raises(BackupError):
        backups.create_backup(
            f"sqlite:///{(tmp_path / 'missing.db').as_posix()}", tmp_path, created_by="a"
        )


def test_list_backups_newest_first(db):
    url, _, backup_dir = db
    first = backups.create_backup(url, backup_dir, created_by="a")
    second = backups.create_backup(url, backup_dir, created_by="b", reason="other")
    assert [b.file_name for b in backups.list_backups(backup_dir)] == [
        second.file_name,
        first.file_name,
    ]


def test_list_backups_of_a_missing_folder_is_empty(tmp_path):
    assert backups.list_backups(tmp_path / "nothing") == []


def test_backup_without_manifest_is_still_listed(db):
    url, _, backup_dir = db
    info = backups.create_backup(url, backup_dir, created_by="a")
    info.path.with_suffix(".json").unlink()
    listed = backups.list_backups(backup_dir)
    assert listed[0].file_name == info.file_name
    assert listed[0].created_by == "desconocido"


def test_corrupt_manifest_is_ignored(db):
    url, _, backup_dir = db
    info = backups.create_backup(url, backup_dir, created_by="a")
    info.path.with_suffix(".json").write_text("{not json", encoding="utf-8")
    assert backups.list_backups(backup_dir)[0].reason == "desconocido"


def test_find_backup_rejects_paths_outside_the_folder(db):
    url, _, backup_dir = db
    info = backups.create_backup(url, backup_dir, created_by="a")
    assert backups.find_backup(backup_dir, info.file_name).file_name == info.file_name
    for bad in ["../mes.db", "sub/x.db", "x.txt", "missing.db"]:
        with pytest.raises(BackupError):
            backups.find_backup(backup_dir, bad)


def test_verify_backup_detects_a_corrupt_file(tmp_path):
    broken = tmp_path / "broken.db"
    broken.write_bytes(b"this is not a database at all" * 100)
    with pytest.raises(BackupError):
        backups.verify_backup(broken)
    with pytest.raises(BackupError):
        backups.verify_backup(tmp_path / "missing.db")


# ---------------------------------------------------------------------------------------------
# Course reset
# ---------------------------------------------------------------------------------------------
def reset(db, level, *, role=Role.ADMIN, confirmation=CONFIRMATION_WORD):
    url, engine, backup_dir = db
    return course_reset.reset_course(
        engine, url, backup_dir, level, actor="admin", actor_role=role, confirmation=confirmation
    )


def test_preview_counts_what_each_level_would_delete(db):
    _, engine, _ = db
    populate(engine)
    with Session(engine) as session:
        production = course_reset.preview(session, ResetLevel.PRODUCTION)
        everything = course_reset.preview(session, ResetLevel.EVERYTHING)
    assert production == {
        "execution_records": 1,
        "downtime_events": 1,
        "units": 1,
        "work_orders": 1,
    }
    assert everything["products"] == 1
    assert everything["users"] == 2  # the operator and the engineer, not the admin


def test_production_reset_keeps_catalogs_and_users(db):
    _, engine, _ = db
    populate(engine)
    result = reset(db, ResetLevel.PRODUCTION)
    assert result.deleted["work_orders"] == 1
    assert count(engine, WorkOrder) == count(engine, Unit) == count(engine, ExecutionRecord) == 0
    assert count(engine, DowntimeEvent) == 0
    assert count(engine, Product) == 1
    assert count(engine, Recipe) == 1
    assert count(engine, User) == 3


def test_catalog_reset_keeps_stations_and_users(db):
    _, engine, _ = db
    populate(engine)
    reset(db, ResetLevel.CATALOGS)
    assert count(engine, Product) == count(engine, Recipe) == count(engine, RecipeStep) == 0
    assert count(engine, Station) == 1
    assert count(engine, User) == 3


def test_full_reset_keeps_only_administrators_and_stations(db):
    _, engine, _ = db
    populate(engine)
    result = reset(db, ResetLevel.EVERYTHING)
    assert result.deleted["users"] == 2
    with Session(engine) as session:
        assert [u.username for u in session.exec(select(User)).all()] == ["admin"]
    assert count(engine, Station) == 1


def test_reset_makes_a_backup_with_the_data_first(db):
    _, engine, backup_dir = db
    populate(engine)
    result = reset(db, ResetLevel.EVERYTHING)
    assert result.backup.row_counts["work_orders"] == 1
    assert "course-reset-everything" in result.backup.file_name
    assert backups.list_backups(backup_dir)[0].file_name == result.backup.file_name


def test_reset_is_recorded_in_the_audit_log(db):
    _, engine, _ = db
    populate(engine)
    result = reset(db, ResetLevel.PRODUCTION)
    with Session(engine) as session:
        entry = audit.list_recent(session)[0]
    assert entry.action == "course_reset"
    assert entry.actor == "admin"
    assert entry.detail["level"] == "production"
    assert entry.detail["backup"] == result.backup.file_name


def test_audit_log_survives_a_full_reset(db):
    _, engine, _ = db
    populate(engine)
    reset(db, ResetLevel.PRODUCTION)
    reset(db, ResetLevel.EVERYTHING)
    assert count(engine, AuditEntry) == 2


@pytest.mark.parametrize("role", [Role.PROCESS_ENGINEER, Role.SUPERVISOR, Role.OPERATOR])
def test_only_admin_can_reset(db, role):
    with pytest.raises(PermissionDeniedError):
        reset(db, ResetLevel.PRODUCTION, role=role)


@pytest.mark.parametrize("word", ["", "reiniciar", "SI", "REINICIA"])
def test_reset_requires_the_confirmation_word(db, word):
    _, engine, backup_dir = db
    populate(engine)
    with pytest.raises(ValidationError) as exc:
        reset(db, ResetLevel.PRODUCTION, confirmation=word)
    assert exc.value.code == "confirmation"
    assert count(engine, WorkOrder) == 1
    assert backups.list_backups(backup_dir) == []


def test_failed_backup_deletes_nothing(db, monkeypatch):
    _, engine, _ = db
    populate(engine)

    def broken(*_args, **_kwargs):
        raise BackupError("disk full")

    monkeypatch.setattr(backups, "create_backup", broken)
    with pytest.raises(BackupError):
        reset(db, ResetLevel.EVERYTHING)
    assert count(engine, WorkOrder) == 1


def test_manual_backup_is_audited(db):
    url, engine, backup_dir = db
    info = course_reset.backup_now(engine, url, backup_dir, actor="admin", actor_role=Role.ADMIN)
    with Session(engine) as session:
        entry = audit.list_recent(session)[0]
    assert (entry.action, entry.detail["backup"]) == ("backup_created", info.file_name)


def test_manual_backup_requires_admin(db):
    url, engine, backup_dir = db
    with pytest.raises(PermissionDeniedError):
        course_reset.backup_now(engine, url, backup_dir, actor="x", actor_role=Role.SUPERVISOR)


def test_audit_list_is_newest_first_and_limited(session):
    for index in range(5):
        audit.record(session, actor="a", action=f"action-{index}", detail={})
    session.commit()
    recent = audit.list_recent(session, limit=3)
    assert [entry.action for entry in recent] == ["action-4", "action-3", "action-2"]


# ---------------------------------------------------------------------------------------------
# User administration
# ---------------------------------------------------------------------------------------------
def test_update_user_name_and_role(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session:
        users.update_user(
            session, ids["student"], full_name=" Ana ", role=Role.SUPERVISOR, actor_id=ids["admin"]
        )
        session.commit()
        user = users.get_user(session, ids["student"])
        assert (user.full_name, user.role) == ("Ana", Role.SUPERVISOR)


def test_admin_cannot_change_own_role(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session, pytest.raises(ValidationError) as exc:
        users.update_user(
            session, ids["admin"], full_name="Admin", role=Role.OPERATOR, actor_id=ids["admin"]
        )
    assert exc.value.code == "self_action"


def test_last_admin_cannot_be_demoted_by_another_user(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session, pytest.raises(ValidationError) as exc:
        users.update_user(
            session, ids["admin"], full_name="Admin", role=Role.OPERATOR, actor_id=ids["engineer"]
        )
    assert exc.value.code == "last_admin"


def test_admin_can_be_demoted_when_another_admin_exists(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session:
        users.update_user(
            session, ids["engineer"], full_name="Ing", role=Role.ADMIN, actor_id=ids["admin"]
        )
        users.update_user(
            session,
            ids["engineer"],
            full_name="Ing",
            role=Role.PROCESS_ENGINEER,
            actor_id=ids["admin"],
        )
        session.commit()


def test_update_user_requires_a_name(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session, pytest.raises(ValidationError) as exc:
        users.update_user(
            session, ids["student"], full_name=" ", role=Role.OPERATOR, actor_id=ids["admin"]
        )
    assert exc.value.field == "full_name"


def test_deactivate_and_reactivate_a_user(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session:
        users.set_user_active(session, ids["student"], False, actor_id=ids["admin"])
        session.commit()
        assert users.authenticate(session, "alumno", "secret123") is None
        users.set_user_active(session, ids["student"], True, actor_id=ids["admin"])
        session.commit()
        assert users.authenticate(session, "alumno", "secret123") is not None


def test_admin_cannot_deactivate_themselves(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session, pytest.raises(ValidationError) as exc:
        users.set_user_active(session, ids["admin"], False, actor_id=ids["admin"])
    assert exc.value.code == "self_action"


def test_last_admin_cannot_be_deactivated(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session, pytest.raises(ValidationError) as exc:
        users.set_user_active(session, ids["admin"], False, actor_id=ids["engineer"])
    assert exc.value.code == "last_admin"


def test_set_password(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session:
        users.set_password(session, ids["student"], "nueva-clave")
        session.commit()
        assert users.authenticate(session, "alumno", "nueva-clave") is not None
        assert users.authenticate(session, "alumno", "secret123") is None
        with pytest.raises(ValidationError):
            users.set_password(session, ids["student"], "corta")


def test_user_with_history_cannot_be_deleted(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session:
        assert users.user_usage(session, ids["student"]) == {
            "execution records": 1,
            "downtime events": 1,
        }
        with pytest.raises(InUseError):
            users.delete_user(session, ids["student"], actor_role=Role.ADMIN, actor_id=ids["admin"])


def test_admin_deletes_a_user_without_history(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session:
        users.delete_user(session, ids["engineer"], actor_role=Role.ADMIN, actor_id=ids["admin"])
        session.commit()
        assert users.get_user_by_username(session, "ing") is None


def test_delete_user_rules(db):
    _, engine, _ = db
    ids = populate(engine)
    with Session(engine) as session:
        with pytest.raises(ValidationError):
            users.delete_user(session, ids["admin"], actor_role=Role.ADMIN, actor_id=ids["admin"])
        with pytest.raises(ValidationError) as exc:
            users.delete_user(
                session, ids["admin"], actor_role=Role.ADMIN, actor_id=ids["engineer"]
            )
        assert exc.value.code == "last_admin"
        with pytest.raises(PermissionDeniedError):
            users.delete_user(
                session, ids["engineer"], actor_role=Role.SUPERVISOR, actor_id=ids["student"]
            )
