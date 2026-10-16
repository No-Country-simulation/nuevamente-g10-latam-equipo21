# Contribución al Proyecto

## Convención de Commits

En este proyecto utilizamos la especificación de **Conventional Commits** para mantener un historial de cambios legible y automatizable.

El formato de un mensaje de commit debe ser:

```
<tipo>(<alcance opcional>): <descripción breve>

[cuerpo opcional]

[pie opcional]
```

### Tipos permitidos
- `feat`: Una nueva funcionalidad (ej: `feat(NM-04): add text extraction service`)
- `fix`: Corrección de un error
- `docs`: Cambios en la documentación
- `style`: Cambios que no afectan el significado del código (espacios en blanco, formato, etc.)
- `refactor`: Un cambio en el código que ni corrige un error ni añade una funcionalidad
- `perf`: Un cambio en el código que mejora el rendimiento
- `test`: Añadir pruebas faltantes o corregir pruebas existentes
- `chore`: Cambios en el proceso de construcción o herramientas auxiliares

### Ticket ID
Siempre que sea posible, incluye el ID del ticket en el alcance, por ejemplo `(NM-03)`.
