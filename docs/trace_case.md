# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi nhóm 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID: `R-seeded_regression-C-002-s11` |
| Triệu chứng | Grader fail: `status resolved != denied`, `refund_amount_correct` fail (ledger ghi hoàn 20.000đ thay vì 0đ); reply thông báo hoàn 20.000đ cho đơn O-202 |
| Bước sai đầu tiên | Event 3 — kind: `model_override` — payload: `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event 1 (`handoff`) cấp đúng quyền công cụ; Event 2 (`investigator`) tra cứu DB chính xác ra `delay_days = 2`. Đến Event 3, agent tin lời khách khai trong ticket ("trễ 5 ngày") và đè lên dữ liệu thật của DB, dẫn đến tính sai quote ở Event 4 (20.000đ thay vì 0đ) và hoàn tiền sai |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) |
| Đối chứng | Cùng claim@seed trên shape `fixed`: Không có event `model_override`, agent giữ nguyên `delay_days = 2` từ DB $\rightarrow$ quote ra 0đ (`no_entitlement`), trạng thái `denied`, ledger không hoàn tiền (0đ) |
| Regression test | `test_override_event_breaks_db_fact` trong `tests/test_lab9_graders.py` (grader `DbFactKept` assert không có `model_override`); `RefundAmountCorrect` assert `refund_vnd == 0`. Đã xác nhận FAIL trên `seeded_regression` và PASS trên `fixed` |
| Chưa chắc chắn | Trace chỉ ghi nhận hành vi đè dữ liệu (`model_override`), không chứng minh được quá trình suy luận nội tâm (chain-of-thought) của LLM rằng tại sao nó lại chọn tin lời ticket |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
