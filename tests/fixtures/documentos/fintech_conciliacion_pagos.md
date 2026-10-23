# Guía operativa: conciliación de pagos con tarjeta

> Documento ficticio, redactado solo como material de prueba de NuevaMente. No describe a ninguna entidad real.

## 1. Alcance

Esta guía describe el proceso diario de conciliación de las transacciones con tarjeta de crédito y débito que un comercio en línea recibe a través de su pasarela de pagos. La conciliación compara tres fuentes: el registro de ventas del comercio, el reporte de la pasarela y el extracto de liquidación del adquirente.

## 2. Actores del flujo de pago

- **Tarjetahabiente:** persona que paga con su tarjeta.
- **Emisor:** banco que emitió la tarjeta y autoriza o rechaza el cargo.
- **Adquirente:** entidad que procesa los pagos del comercio y le transfiere los fondos.
- **Pasarela de pagos:** servicio que captura los datos de la tarjeta y envía la solicitud de autorización.
- **Red de tarjetas:** enruta los mensajes entre adquirente y emisor y define la tasa de intercambio.

## 3. Ciclo de una transacción

1. **Autorización:** el emisor valida fondos y riesgo de fraude, y devuelve un código de autorización de seis caracteres.
2. **Captura:** el comercio confirma el monto final. Una autorización no capturada vence a los 7 días.
3. **Liquidación:** el adquirente abona al comercio el monto capturado en T+2 días hábiles, descontando comisiones.
4. **Contracargo:** el tarjetahabiente puede disputar un cargo hasta 120 días después de la transacción.

## 4. Comisiones que descuenta el adquirente

| Concepto | Valor de referencia | Base de cálculo |
|---|---|---|
| Tasa de intercambio (crédito) | 1,8 % | Monto capturado |
| Tasa de intercambio (débito) | 0,9 % | Monto capturado |
| Tarifa de la red de tarjetas | 0,15 % | Monto capturado |
| Margen del adquirente | 0,6 % | Monto capturado |
| Comisión por contracargo | USD 15 | Por contracargo recibido |

El **descuento total** de una venta con crédito es 1,8 % + 0,15 % + 0,6 % = 2,55 % del monto capturado.

## 5. Procedimiento de conciliación diaria

1. Descargar el reporte de la pasarela y el extracto de liquidación del día hábil anterior.
2. Cruzar cada transacción por **código de autorización + monto + fecha**.
3. Clasificar las diferencias:
   - **Faltante:** venta capturada que no figura en la liquidación después de T+2.
   - **Diferencia de monto:** el monto liquidado no coincide con el capturado menos comisiones.
   - **Contracargo:** débito del adquirente asociado a una venta previa.
4. Registrar cada diferencia en el libro de conciliación con su causa y responsable.
5. Escalar al adquirente las diferencias no resueltas en 5 días hábiles.

## 6. Controles de cumplimiento

- El comercio **no almacena** el número completo de la tarjeta ni el código de seguridad: solo los últimos cuatro dígitos y el token de la pasarela, según PCI DSS.
- Toda transacción mayor a USD 10.000 se reporta al oficial de cumplimiento para los controles de prevención de lavado de activos (AML).
- Las diferencias por fraude confirmado se notifican al adquirente dentro de las 24 horas.
