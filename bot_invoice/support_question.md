# Вопрос в поддержку Quick Resto — создание приходной через открытое API

## Суть
Создание приходной накладной (`IncomingInvoice`) через открытое API стабильно
возвращает **HTTP 500 / `java.lang.NullPointerException`**. Чтение, список и удаление
существующих накладных через то же API работают штатно. Нужен рабочий способ/пример
**создания** приходной с позициями.

## Эндпоинт и объект
- `POST /platform/online/api/update?moduleName=warehouse.documents.incoming&className=ru.edgex.quickresto.modules.warehouse.documents.incoming.IncomingInvoice`
- Basic Auth, `Content-Type: application/json`. Создание = объект без `id` (upsert).

## Что отправляем (минимальный payload, одна позиция)
Ссылки взяты из реального объекта, полученного через `GET /api/read` (т.е. классы и id
заведомо валидны: поставщик `Businessman`/`Organization`, товар `SingleProduct`, склад
`Store`, единица `MeasureUnit`, объект `vat`). Расчётные поля (`calculated*`, `fixed*`,
`costPrice*`, `storeQuantity*`, `prevPrice`) не передаём — их считает сервер.

```json
{
  "className": "ru.edgex.quickresto.modules.warehouse.documents.incoming.IncomingInvoice",
  "documentNumber": "TEST-API-DELETE",
  "invoiceDate": "2026-06-05T15:00:00.000Z",
  "paymentDate": "2026-06-05T15:00:00.000Z",
  "paid": false,
  "processed": false,
  "provider": { "className": "ru.edgex.quickresto.modules.warehouse.providers.Businessman", "id": 2 },
  "store":    { "className": "ru.edgex.quickresto.modules.warehouse.store.Store", "id": 1 },
  "invoiceItems": [
    {
      "className": "ru.edgex.quickresto.modules.warehouse.documents.items.common.InvoiceItem",
      "product":     { "className": "ru.edgex.quickresto.modules.warehouse.nomenclature.singleproduct.SingleProduct", "id": 9 },
      "measureUnit": { "className": "ru.edgex.quickresto.modules.core.dictionaries.measureunits.MeasureUnit", "id": 2 },
      "actualAmount": 2.46,
      "price": 328.57143,
      "priceWithVat": 345.0,
      "vat": { "id": 4, "deleted": false, "value": 5.0, "taxType": "priceIncludesVat" }
    }
  ]
}
```

## Стек ошибки (root cause)
```
java.lang.NullPointerException
  PrimeCostCalculator.setStoreDocumentItemStoreState(PrimeCostCalculator.java:348)
  PrimeCostCalculator.setStoreDocumentItemStoreState(PrimeCostCalculator.java:335)
  PrimeCostCalculator.setStoreDocumentItemStoreState(PrimeCostCalculator.java:330)
  PrimeCostCalculator.setStoreDocumentItemStoreState(PrimeCostCalculator.java:325)
  AbstractItemPersistenceService.updateTransientFields(AbstractItemPersistenceService.java:37)
  AbstractItemPersistenceService.read(AbstractItemPersistenceService.java:100)
  InvoiceItemRepository.read(InvoiceItemRepository.java:62)
  CRUDSupportService.expandMapDependencies(CRUDSupportService.java:122)
  ApiController.updateEntity(ApiController.java:606)
```
NPE возникает в расчёте себестоимости (`PrimeCostCalculator`) на этапе чтения позиции
обратно (`updateTransientFields`) внутри `updateEntity`, т.е. **после** записи, при
формировании ответа. Весь `updateEntity` в транзакции → откат → накладная не создаётся.

## Что уже проверено (NPE не меняется)
- payload без единого `className: null` во вложенных ссылках;
- товар класса `SingleProduct` (реальный складской ингредиент) и `Dish` — одинаково;
- наличие/отсутствие объекта `vat` у позиции;
- `processed: false` и `processed: true` (проведение).

## Вопросы
1. Как корректно **создать** приходную накладную с позициями через открытое API?
   Какой минимальный набор полей шапки и позиции обязателен, а что сервер считает сам?
2. Создаются ли шапка и позиции **раздельно** (сначала документ, затем позиции с ссылкой
   на него), или одним объектом с вложенным `invoiceItems`?
3. Нужен рабочий **пример payload** создания приходной (желательно с одной позицией).

## Параллельный вопрос (перечисление номенклатуры)
`/api/list` для `SingleProduct`/`Dish` отдаёт только корень дерева; `filters` в query
игнорируется; внутренний `/platform/data/.../select?parentContextId=` требует сессию
(Basic Auth → 401). Как через открытое API получить **плоский список номенклатуры**
(или детей группы) — чтобы построить карту `артикул → id`?
