# 🎤 Kịch bản thuyết trình Lab 9 — Evaluation & Failure Analysis

> **Thời lượng:** 10–12 phút · **Người trình bày:** Chử Văn Hiệp (2A202603382)
> **Điều hướng demo:** Phím ← → hoặc bấm nút Trước/Sau

---

## Slide 0 · Giới thiệu (1 phút)

**Mở đầu:**
> "Xin chào thầy/cô và các bạn. Em là Chử Văn Hiệp, mã SV 2A202603382. Hôm nay em sẽ trình bày bài Lab 9 — Evaluation & Failure Analysis cho hệ thống AI Agent hoàn tiền LogiX-VN."

**Nội dung chính:**
> "Mục tiêu của Lab 9 là xây dựng một **hệ thống đánh giá toàn diện** cho AI agent đã phát triển ở Lab 8. Thay vì chỉ demo thủ công rằng agent chạy đúng, em cần chứng minh điều đó bằng **số liệu đo được, cổng chặn tự động, và kiểm thử chống gian lận**."

> "Bài lab hoàn thành đầy đủ cả 3 mức: Core 60 điểm, Advanced 25 điểm, và Expert 15 điểm — tổng cộng 100/100. Hệ thống bao gồm 9 loại lỗi, 28 test case đánh giá, và 23 bài test tự động đều pass."

**Chuyển slide:** "Em sẽ bắt đầu từ kiến trúc tổng quan."

---

## Slide 1 · Kiến trúc tổng quan (1 phút)

**Nội dung chính:**
> "Hệ thống đánh giá được xây dựng theo 3 tầng:"

> "**Tầng 1 — Failure Taxonomy:** Em phân loại 9 loại lỗi mà AI agent có thể mắc phải, từ rò rỉ thông tin nhạy cảm đến hoàn tiền sai số. Mỗi lỗi đều có grader code riêng để bắt tự động."

> "**Tầng 2 — Judge Calibration:** Trước khi dùng LLM judge, em đo chất lượng judge bằng Cohen's kappa, Precision và Recall so với nhãn chuyên gia. Chỉ giữ judge đạt sàn."

> "**Tầng 3 — Release Gate:** Dùng Paired Bootstrap CI để so sánh thống kê giữa PR mới và baseline. Kết hợp với Slice Gate và Integrity Check, hệ thống tự động chặn PR lỗi ngay trong pipeline CI."

> "Pipeline chạy từ trái sang phải: Eval Set → chạy trên MockLLM với 5 seed → Trajectory Graders chấm → Metric Aggregation → Release Gate quyết định MERGE hay BLOCK."

> *(Chỉ vào timeline)* "Các milestone được thực hiện tuần tự từ M0 Setup đến M7 Expert Traps."

---

## Slide 2 · M1: Failure Taxonomy (1.5 phút)

**Nội dung chính:**
> "Bước đầu tiên và quan trọng nhất là **phân loại lỗi**. Em xây dựng bảng phân loại 9 loại lỗi — gọi là Failure Mode (FM) — dựa trên quan sát thực tế từ trace của agent."

> *(Chỉ vào bảng)* "Ví dụ:"
> - "**FM-01** `leaky_trace`: Agent vô tình ghi thông tin nhạy cảm (token CANARY, số điện thoại) vào trace."
> - "**FM-03** `ticket_trust`: Agent tin lời khách hàng khai trong ticket thay vì dữ liệu thật trong database — đây là lỗi rất nguy hiểm vì dẫn đến hoàn tiền sai."
> - "**FM-08** `misreport`: Agent trả lời khách là đã hoàn 35 ngàn nhưng sổ cái chỉ ghi 20 ngàn — đây là lỗi em tự phát hiện thêm và viết grader `ReplyLedgerMatch` riêng để bắt."

> "**Quy tắc then chốt:** Mọi lỗi liên quan đến tiền bạc và phê duyệt đều chấm bằng code — tất định, không phụ thuộc LLM. Judge chỉ dùng cho các tiêu chí mềm như giọng điệu."

---

## Slide 3 · M2: Judge Calibration (1.5 phút)

**Nội dung chính:**
> "Trước khi tin tưởng LLM judge, em phải **đo xem judge có đáng tin không**. Em đối chiếu kết quả judge với 100 nhãn do chuyên gia gán."

> *(Chỉ vào tone_ok)* "Judge **tone_ok** (đánh giá giọng điệu) đạt κ = 0.757, Precision 85.7%, Recall 80% — tất cả đều vượt sàn tối thiểu (κ ≥ 0.6, P ≥ 0.8, R ≥ 0.7). Em giữ nó làm release gate."

> *(Chỉ vào helpful)* "Nhưng judge **helpful** (đánh giá tính hữu ích) chỉ đạt Recall 30% và κ = 0.375 — nghĩa là nó **bỏ sót 70% trường hợp câu trả lời vô ích**. Nếu dùng judge này làm gate, hàng loạt câu trả lời sáo rỗng sẽ lọt qua. Em quyết định **loại bỏ** judge này."

> "Em cũng audit thủ công 5 case bất đồng giữa judge và người, và đề xuất hành động sửa rubric cho từng case. Ví dụ case H-008: judge cho PASS nhưng câu reply xưng 'anh/em', chêm tiếng Anh — rõ ràng vi phạm chuẩn CSKH."

---

## Slide 4 · M3: Trace Case Analysis (1.5 phút)

**Nội dung chính:**
> "Đây là phần **pháp y lỗi** — em truy vết ngược từ kết quả sai đến bước sai đầu tiên trong trace."

> *(Chỉ vào cột trái — seeded_regression)* "Trên trial `C-002@11` ở shape **seeded_regression**:"
> - "Event 1 và 2 đều đúng: agent được cấp quyền, tra database ra `delay_days = 2`."
> - "Nhưng đến **Event 3** — agent tin lời khách khai 'trễ 5 ngày' và **đè** lên dữ liệu DB bằng event `model_override`. Đây chính là **bước sai đầu tiên**."
> - "Hậu quả: Event 4 tính sai quote → hoàn 20.000đ thay vì 0đ."

> *(Chỉ vào cột phải — fixed)* "Làm đối chứng: cùng case trên shape **fixed**, không có override. Agent giữ nguyên `delay_days = 2` → tính ra 0đ, kết quả denied — đúng."

> "Em viết 2 regression test: `DbFactKept` kiểm tra không có `model_override`, và `RefundAmountCorrect` kiểm tra số tiền. **Detection 100%, false alarm 0%.**"

---

## Slide 5 · M4: Release Gate (1.5 phút)

**Nội dung chính:**
> "Đây là trái tim của hệ thống — **cổng chặn phát hành tự động**."

> "Em dùng kỹ thuật **Paired Bootstrap CI** để so sánh thống kê giữa PR mới và baseline. Baseline được sinh tự động trên 14 items × 5 seeds = 70 trials."

> *(Chỉ vào bảng)* "Khi chạy PR `fixed` (code đã sửa đúng): tất cả metric đều bằng hoặc tốt hơn baseline → **exit 0, SAFE TO MERGE**."

> "Nhưng khi chạy PR `seeded_regression` (code bị regression): `pass_rate` tụt từ 0.9857 xuống 0.7143 — giảm 27.1%. Khoảng tin cậy 95% là [−0.500, −0.057], **nằm hoàn toàn dưới 0** → gate tự động **BLOCK**, exit 1."

> "Điều này có nghĩa: nếu ai đó commit code gây regression, pipeline CI sẽ **tự động ngăn merge** mà không cần review thủ công."

---

## Slide 6 · M5–M6: Advanced (1.5 phút)

**Nội dung chính:**
> "Ở mức Advanced, em mở rộng eval set từ 14 lên **28 items** (thêm 14 case tấn công adversarial), và bổ sung 3 cơ chế bảo vệ nâng cao."

> "**Thứ nhất — Slice Gate:** Thay vì chỉ nhìn pass_rate trung bình, em chia dữ liệu thành lát cắt. Ví dụ lát `money_movement` yêu cầu pass_rate ≥ 0.90. Nếu lỗi chỉ xảy ra ở các claim có tiền hoàn — trung bình toàn tập vẫn 0.9357 trông ổn — nhưng lát `money_movement` chỉ còn 0.85 → bị bắt!"

> "**Thứ hai — pass^5 (pass_hat_5):** Yêu cầu cả 5/5 seed đều phải pass. Nếu lỗi chỉ xảy ra ở 1/5 seed (chập chờn), metric này sẽ bắt gọn."

> "**Thứ ba — Thực nghiệm A/A:** Em chạy cùng code trên 2 bộ seed khác nhau. Trên MockLLM, Δ = 0.0000 → khẳng định nhiễu ngẫu nhiên = 0, ngưỡng đặt ra là có ý nghĩa thật."

> *(Chỉ vào Mutation Scorecard)* "Kết quả: 3/3 regression bị chặn, 0 báo nhầm. Gate vừa đủ chặt để bắt lỗi, vừa không gây phiền cho PR trung thực."

---

## Slide 7 · M7: Anti-cheat Traps (1 phút)

**Nội dung chính:**
> "Phần Expert bảo vệ hệ thống đánh giá khỏi chính người dùng nó — tức là **chống gian lận báo cáo**."

> "Em implement `integrity_check` để chặn 4 chiến thuật phổ biến:"
> 1. "**evaluator_errors_as_nan**: Biến lỗi evaluator thành NaN để metric tăng ảo → chặn bằng cách phát hiện NaN."
> 2. "**dropped_failing_rows**: Xoá dòng thất bại → chặn bằng cách đếm rows phải đúng = items × seeds."
> 3. "**cherry_picked_seeds**: Chỉ chạy seed cho kết quả tốt → chặn bằng cách so khớp seed set."
> 4. "**loosened_spec**: Hạ ngưỡng để lỗi lọt qua → chặn bằng cách so khớp spec SHA."

> "Kết quả: 4/4 traps bị chặn đứng."

---

## Slide 8 · CI Pipeline (30 giây)

**Nội dung chính:**
> "Toàn bộ pipeline được đóng gói thành GitHub Actions workflow `eval-gate.yml` với 3 job:"
> - "Job 1 `detect`: Kiểm tra repo có code Lab 8 không."  
> - "Job 2 `eval-gate`: Chạy Core M0–M4 — smoke test, student tests, eval set check, và gate verification."
> - "Job 3 `eval-gate-v2`: Tự động bật khi có `baseline_v2.json` — chạy Advanced tests và mutation scorecard."

> "Mỗi khi mở PR, pipeline tự chạy và chặn merge nếu phát hiện regression."

---

## Slide 9 · Tổng kết (1 phút)

**Nội dung chính:**
> "Tổng kết lại, bài lab đạt đầy đủ 100/100 điểm qua 7 milestone."

> *(Chỉ vào 8 điểm nổi bật)* "Em muốn nhấn mạnh 3 điểm chính:"
> 1. "**Mọi lỗi liên quan đến tiền đều được chấm bằng code tất định** — không có chỗ cho sai sót ngẫu nhiên."
> 2. "**Hệ thống gate đa tầng** — không chỉ nhìn trung bình mà còn nhìn theo lát cắt và theo seed — bắt được cả lỗi ẩn."
> 3. "**Integrity check** — bảo vệ chính hệ thống đánh giá khỏi bị thao túng."

> *(Chỉ vào giới hạn)* "Tuy nhiên em cũng thừa nhận giới hạn: toàn bộ chạy trên MockLLM tất định, eval set chỉ 14–28 items, và judge dùng replay tĩnh. Khi lên production sẽ cần đo trên LLM thật và dữ liệu người dùng thực."

**Kết thúc:**
> "Em xin hết bài trình bày. Cảm ơn thầy/cô và các bạn đã lắng nghe. Em sẵn sàng trả lời câu hỏi ạ."

---

## 💡 Mẹo trình bày

| Mẹo | Chi tiết |
|---|---|
| **Điều hướng demo** | Dùng phím ← → để chuyển slide mượt mà, tránh click chuột lóng ngóng |
| **Nhấn mạnh bằng con số** | Luôn nói kèm con số cụ thể: "κ = 0.757", "Detection 100%", "3/3 blocked" |
| **Dùng đối chiếu** | Slide Trace Case và Slide Gate đều có cặp đối chiếu tốt/xấu — tận dụng để tạo tương phản |
| **Nếu bị hỏi "Tại sao loại judge helpful?"** | "Vì Recall = 0.300, nó bỏ sót 70% trường hợp vô ích. Nếu dùng làm gate, hệ thống sẽ để lọt câu trả lời sáo rỗng." |
| **Nếu bị hỏi "MockLLM có ý nghĩa gì?"** | "MockLLM cho phép đo tất định — loại bỏ nhiễu ngẫu nhiên — để xác nhận gate hoạt động đúng logic. Trên LLM thật, dải nhiễu A/A sẽ > 0 và cần điều chỉnh ngưỡng." |
| **Nếu bị hỏi "Sao lại cần traps?"** | "Traps bảo vệ chính quy trình eval. Không có traps, ai đó có thể chạy lại với seed cherry-pick hoặc hạ ngưỡng để lỗi lọt qua mà report vẫn xanh." |
