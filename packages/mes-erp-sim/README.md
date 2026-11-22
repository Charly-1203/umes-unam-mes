# mes-erp-sim

Simulador de ERP (nivel 4 de ISA-95).

No implementa un ERP: solo envía órdenes de producción y listas de materiales (BOM)
al servidor del MES para demostrar la integración entre niveles.

## Regla clave

Se comunica con el servidor únicamente a través de su API pública, igual que lo
haría un ERP real.

## Ejecución

```powershell
uv run mes-erp-sim --version
```
