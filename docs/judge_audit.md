# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | Dùng làm gate |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không đạt (R=0.300 < 0.7, κ=0.375 < 0.6) | Loại bỏ |

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric |
|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người đúng | Reply: "Em đã hoàn tiền cho anh rồi nha, anh check giúp em." -> Văn phong suồng sã, xưng hô anh/em, chêm từ "check", "nha". Sửa rubric: Cấm tuyệt đối tiếng lóng, từ chêm tiếng Anh, yêu cầu đại từ chuẩn ("LogiX - Quý khách/Anh/Chị"). |
| 2 | H-017 | PASS | FAIL | Người đúng | Reply: "Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha." -> Khẩu ngữ "bạn ơi", "rồi nha" không phù hợp kênh CSKH chính thức. Sửa rubric: Quy định văn phong trang trọng, chuẩn mực. |
| 3 | H-029 | PASS | FAIL | Người đúng | Reply: "Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm." -> Sắc thái gạt bỏ khách hàng (dismissive), cộc cằn. Sửa rubric: Định nghĩa hành vi cộc cằn, thiếu thiện chí là vi phạm nghiêm trọng (FAIL). |
| 4 | H-042 | FAIL | PASS | Người đúng | Reply: "Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ." -> Câu văn súc tích, đủ kính ngữ "Dạ/ạ" và thời hạn cụ thể. Judge báo nhầm (FP). Sửa rubric: Nêu rõ câu trả lời ngắn gọn, trực diện vấn đề vẫn đạt chuẩn. |
| 5 | HL-016 | PASS | FAIL | Người đúng | Reply: "Dạ, LogiX thành thật xin lỗi anh/chị vì sự bất tiện này..." -> Chỉ xin lỗi sáo rỗng mà không đưa ra giải pháp hay thông tin xử lý khiếu nại. Judge bị đánh lừa bởi thái độ lịch sự. Sửa rubric: Phải có hành động giải quyết cụ thể mới tính là helpful. |

## Kết luận
- **Tiêu chí bị loại:** `helpful` bị loại vì ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` cho thấy Recall cực thấp (0.300) — bỏ sót tới 21/30 trường hợp câu trả lời vô ích (lọt lưới 70%), $\kappa = 0.375 < 0.6$. Nếu đưa `helpful` làm gate phát hành, hệ thống sẽ để lọt hàng loạt câu trả lời vô nghĩa.
- **Rủi ro còn lại:** Cả hai judge hiện chỉ được kiểm định trên dữ liệu replay tĩnh đã công khai (`judge_tone_public.csv`, `judge_helpful_public.csv`). Cần thu thập dữ liệu người dùng thật với nhãn chuyên gia mới để tạo tập kiểm thử mù (held-out test set) định kỳ.
