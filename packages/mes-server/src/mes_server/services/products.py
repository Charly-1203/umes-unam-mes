"""Products and their bills of materials."""

from sqlmodel import Session, select

from mes_core.enums import Role
from mes_server.db.models import BomItem, Product, Recipe, WorkOrder
from mes_server.services import catalog
from mes_server.services.errors import AlreadyExistsError, NotFoundError, ValidationError
from mes_server.services.validation import normalize_code, optional_text, required_text

REFERENCES = (
    catalog.Reference("recipes", Recipe.product_id),
    catalog.Reference("work orders", WorkOrder.product_id),
)
"""Records that point at a product and therefore keep it from being deleted."""


# ---------------------------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------------------------
def list_products(session: Session, *, include_inactive: bool = False) -> list[Product]:
    """Return products ordered by code.

    Args:
        session: Open database session.
        include_inactive: Also return deactivated products.

    Returns:
        The products.
    """
    statement = select(Product).order_by(Product.code)
    if not include_inactive:
        statement = statement.where(Product.is_active == True)  # noqa: E712
    return list(session.exec(statement).all())


def get_product(session: Session, product_id: int) -> Product:
    """Load a product.

    Args:
        session: Open database session.
        product_id: Primary key.

    Returns:
        The product.

    Raises:
        NotFoundError: If it does not exist.
    """
    return catalog.get_or_raise(session, Product, product_id)


def create_product(
    session: Session, *, code: str, name: str, description: str | None = None
) -> Product:
    """Create a product.

    Args:
        session: Open database session. The caller commits.
        code: Unique code, normalized to uppercase.
        name: Human-readable name.
        description: Optional free text.

    Returns:
        The new product.

    Raises:
        ValidationError: If a field breaks the rules.
        AlreadyExistsError: If the code is taken.
    """
    normalized = normalize_code(code, max_length=64)
    product = Product(
        code=normalized,
        name=required_text(name, field="name", max_length=128),
        description=optional_text(description, field="description", max_length=512),
    )
    catalog.ensure_code_available(session, Product, normalized)
    session.add(product)
    session.flush()
    return product


def update_product(
    session: Session, product_id: int, *, name: str, description: str | None = None
) -> Product:
    """Change a product's name and description. The code never changes.

    Args:
        session: Open database session. The caller commits.
        product_id: Primary key.
        name: New name.
        description: New description.

    Returns:
        The updated product.

    Raises:
        NotFoundError: If it does not exist.
        ValidationError: If a field breaks the rules.
    """
    product = get_product(session, product_id)
    product.name = required_text(name, field="name", max_length=128)
    product.description = optional_text(description, field="description", max_length=512)
    session.add(product)
    return product


def set_product_active(session: Session, product_id: int, active: bool) -> Product:
    """Activate or deactivate a product.

    Args:
        session: Open database session. The caller commits.
        product_id: Primary key.
        active: New state.

    Returns:
        The product.
    """
    product = get_product(session, product_id)
    catalog.set_active(product, active)
    session.add(product)
    return product


def product_usage(session: Session, product_id: int) -> dict[str, int]:
    """Count the records that reference a product.

    Args:
        session: Open database session.
        product_id: Primary key.

    Returns:
        Non-zero counts keyed by reference label.
    """
    return catalog.count_references(session, product_id, REFERENCES)


def delete_product(session: Session, product_id: int, *, actor_role: Role) -> None:
    """Delete a product without history, together with its bill of materials.

    Args:
        session: Open database session. The caller commits.
        product_id: Primary key.
        actor_role: Role of the user asking for the deletion.

    Raises:
        NotFoundError: If it does not exist.
        PermissionDeniedError: If the role is not an administrator.
        InUseError: If recipes or work orders reference it.
    """
    product = get_product(session, product_id)
    catalog.delete_unused(session, product, product_id, REFERENCES, actor_role=actor_role)


# ---------------------------------------------------------------------------------------------
# Bill of materials
# ---------------------------------------------------------------------------------------------
def _validate_quantity(quantity: float) -> float:
    try:
        value = float(quantity)
    except (TypeError, ValueError):
        raise ValidationError(
            "Quantity must be a number.", code="not_a_number", field="quantity"
        ) from None
    if value <= 0:
        raise ValidationError(
            "Quantity must be greater than zero.", code="not_positive", field="quantity"
        )
    return value


def _ensure_component_available(
    session: Session, product_id: int, component_code: str, *, exclude_id: int | None = None
) -> None:
    statement = select(BomItem).where(
        BomItem.product_id == product_id, BomItem.component_code == component_code
    )
    existing = session.exec(statement).first()
    if existing is not None and existing.id != exclude_id:
        raise AlreadyExistsError(
            f"Component '{component_code}' is already in the bill of materials.",
            field="component_code",
        )


def add_bom_item(
    session: Session,
    product_id: int,
    *,
    component_code: str,
    quantity: float,
    unit_of_measure: str = "pcs",
    description: str | None = None,
) -> BomItem:
    """Add a component to a product's bill of materials.

    Args:
        session: Open database session. The caller commits.
        product_id: Product the component belongs to.
        component_code: Component code, normalized to uppercase.
        quantity: Amount per unit of product; must be positive.
        unit_of_measure: Unit of ``quantity``.
        description: Optional component description.

    Returns:
        The new line.

    Raises:
        NotFoundError: If the product does not exist.
        ValidationError: If a field breaks the rules.
        AlreadyExistsError: If the component is already listed.
    """
    get_product(session, product_id)
    code = normalize_code(component_code, field="component_code", max_length=64)
    item = BomItem(
        product_id=product_id,
        component_code=code,
        quantity=_validate_quantity(quantity),
        unit_of_measure=required_text(unit_of_measure, field="unit_of_measure", max_length=16),
        description=optional_text(description, field="description", max_length=256),
    )
    _ensure_component_available(session, product_id, code)
    session.add(item)
    session.flush()
    return item


def update_bom_item(
    session: Session,
    item_id: int,
    *,
    component_code: str,
    quantity: float,
    unit_of_measure: str,
    description: str | None = None,
) -> BomItem:
    """Change a line of a bill of materials.

    Args:
        session: Open database session. The caller commits.
        item_id: Primary key of the line.
        component_code: Component code, normalized to uppercase.
        quantity: Amount per unit of product; must be positive.
        unit_of_measure: Unit of ``quantity``.
        description: Optional component description.

    Returns:
        The updated line.

    Raises:
        NotFoundError: If the line does not exist.
        ValidationError: If a field breaks the rules.
        AlreadyExistsError: If another line already lists the component.
    """
    item = session.get(BomItem, item_id)
    if item is None:
        raise NotFoundError(f"BomItem {item_id} does not exist.")
    code = normalize_code(component_code, field="component_code", max_length=64)
    _ensure_component_available(session, item.product_id, code, exclude_id=item_id)
    item.component_code = code
    item.quantity = _validate_quantity(quantity)
    item.unit_of_measure = required_text(unit_of_measure, field="unit_of_measure", max_length=16)
    item.description = optional_text(description, field="description", max_length=256)
    session.add(item)
    return item


def delete_bom_item(session: Session, item_id: int) -> None:
    """Remove a line from a bill of materials.

    Bill of materials lines are part of the product definition, not of the production history,
    so anyone allowed to maintain products may remove them.

    Args:
        session: Open database session. The caller commits.
        item_id: Primary key of the line.

    Raises:
        NotFoundError: If the line does not exist.
    """
    item = session.get(BomItem, item_id)
    if item is None:
        raise NotFoundError(f"BomItem {item_id} does not exist.")
    session.delete(item)
    session.flush()


def list_bom_items(session: Session, product_id: int) -> list[BomItem]:
    """Return a product's bill of materials ordered by component code.

    Args:
        session: Open database session.
        product_id: Product to read.

    Returns:
        The lines.
    """
    statement = (
        select(BomItem).where(BomItem.product_id == product_id).order_by(BomItem.component_code)
    )
    return list(session.exec(statement).all())
