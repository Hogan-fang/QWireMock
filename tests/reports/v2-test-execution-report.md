# V2 Test Execution Report

- Total test cases: 19
- Passed: 19
- Failed: 0
- Skipped: 0

## Case Details
| No. | Test Case | Result | Test Point | Order Keyword |
|---:|---|---|---|---|
| 1 | test_v2_create_order_success_returns_201_and_masked_card | passed | POST /order creates successfully and returns a masked card | 34c853fb-491f-4fea-a20e-659bf9bac1db |
| 2 | test_v2_create_order_conflict_returns_400 | passed | POST /order duplicate reference returns 400 with Order already exists | c5d247ca-706c-40b4-a10e-3082981497fb |
| 3 | test_v2_create_order_invalid_card_returns_400 | passed | POST /order card number starting with 4 returns 400 and FAIL | 992212a8-f494-4023-89cd-9e8743bee887 |
| 4 | test_v2_create_order_invalid_uuid_returns_422 | passed | POST /order invalid UUID in request body returns 422 from framework validation | 1aba8bca-a65b-4954-b459-6757591 |
| 5 | test_v2_get_order_invalid_uuid_returns_400 | passed | GET /order invalid UUID returns 400 | not-a-uuid |
| 6 | test_v2_get_order_not_found_returns_404 | passed | GET /order order not found returns 404 | 283f088b-1e03-4ffb-b613-0c6274d28a92 |
| 7 | test_v2_get_order_found_returns_200 | passed | GET /order successful query returns 200 | f1298eb0-f627-4fc9-967e-01a89c31622f |
| 8 | test_v2_create_then_get_order_flow | passed | Create then query: returns the same reference and orderId | fce491d5-a2ea-4db7-ab6e-3b5ee09029d7 |
| 9 | test_v2_dispatch_callback_skip_by_amount_policy | passed | Amount threshold policy: high amount skips callback, low amount triggers callback | PX1001 |
| 10 | test_v2_integration_create_order_persists_db | passed | Integration: POST /order persists successfully into v2_orders/v2_order_products | 7362cfa7-58bd-4a39-b408-a05c4fdc63f2 |
| 11 | test_v2_integration_invalid_card_persists_fail_order | passed | Integration: card number starting with 4 returns 400 and persists failed order | 6df1cc0d-5980-44cd-a00a-71ec7da7455f |
| 12 | test_v2_integration_get_order_reads_from_db | passed | Integration: GET /order reads and returns data from database | 57d96b7d-510a-469f-98cb-dd06b5327bab |
| 13 | test_v2_integration_duplicate_reference_conflict | passed | Integration: duplicate reference second submit returns 400 and keeps only one record | 87e186f2-9b73-470f-9035-7485ecce488b |
| 14 | test_v2_integration_product_status_transition_30s_60s | passed | Integration: product status becomes SHIPPED at 30s and DELIVERED at 60s, then order becomes COMPLETED | 1d5a8cff-b494-4f96-8ac3-662e65591ab1 |
| 15 | test_v2_integration_order_completed_only_when_all_products_delivered | passed | Integration: in multi-product orders, order becomes COMPLETED only after all products are DELIVERED | 09e712c4-996b-401e-98a0-9fc19339434b |
| 16 | test_v2_callback_receive_returns_ok | passed | POST /callback valid payload returns 200 and callback data is logged only | 577585ac-faf0-41d6-9f52-b656e34c9554 |
| 17 | test_v2_check_not_found_returns_404 | passed | GET /check returns 404 because callbacks are log-only | ba3d78fc-f217-453a-860d-40035a394c91 |
| 18 | test_v2_callback_invalid_payload_returns_400 | passed | POST /callback invalid payload returns 400 with error details | b9f348de-d5b4-44de-84e6-3bcbe01a3177 |
| 19 | test_generate_v2_execution_report | passed | Execution trace sample: record reference and orderId keywords | PX9001 |