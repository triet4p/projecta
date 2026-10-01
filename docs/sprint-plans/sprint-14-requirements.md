# Ghi nhận yêu cầu Sprint 14 và mục tiêu release 1.0.0

Tài liệu này ghi nhận lần lượt các ý kiến của chủ dự án để làm đầu vào xác định phạm vi Sprint 14. Release `1.0.0` là mục tiêu **sau Sprint 14**, không phải trạng thái đã được phê duyệt. Đây chưa phải sprint plan, tiêu chí nghiệm thu hay quyết định mở các gate đang khóa.

## 1. Chức năng riêng lẻ

> Về mặt chức năng, từng chức năng cụ thể đã đủ và oke.

**Ghi nhận:** Chủ dự án đánh giá các chức năng xét riêng lẻ đã đủ và đạt kỳ vọng về mặt chức năng. Chưa có yêu cầu bổ sung chức năng riêng lẻ nào từ ý này. Nhận định này chưa thay thế kiểm chứng tích hợp, đánh giá chất lượng hoặc các điều kiện phát hành; phạm vi Sprint 14 sẽ tiếp tục được xác định từ các ý kiến tiếp theo.

## 2. Rà soát tổng thể UI/UX

**Ghi nhận:** UI/UX hiện có nhiều điểm cần xem lại; các ảnh do chủ dự án cung cấp là ví dụ, không phải danh sách đầy đủ. Sprint 14 cần rà soát và cải thiện tính nhất quán, phân cấp điều hướng và khả năng đọc của giao diện, thay vì coi từng màn hình hiện tại đã hoàn thiện về trải nghiệm.

- **Khu vực đăng nhập/đăng xuất — ảnh #1:** “Signed in” và “Sign out” đứng riêng trên một hàng rộng ở phía trên, tạo khoảng trống và bố cục mất cân đối. Cần bố trí lại thông tin trạng thái phiên và thao tác đăng xuất trong cấu trúc giao diện hợp lý hơn. Đây là nhận xét về trình bày, chưa phải kết luận có lỗi xác thực.
- **Phân cấp project/workspace — ảnh #1:** Header thể hiện “Project workspace” là một project cụ thể (ví dụ “Project Alpha”), nhưng mục chọn **Projects** lại đứng cùng cấp điều hướng với các màn hình bên trong project như **Project Overview**, **Notes**, **Graph** và **Review Queue**. Cần làm rõ ranh giới giữa chọn/đổi project và thao tác trong project đã chọn để người dùng không hiểu chúng là các màn hình cùng cấp.
- **Khả năng đọc graph — ảnh #2:** Các node có nền gần đen trong khi chữ cũng rất tối, khiến tên và trạng thái khó đọc; màu sắc/độ tương phản giữa node, trạng thái và legend chưa giúp phân biệt dễ dàng. Cần rà soát bảng màu và độ tương phản của graph, bảo đảm nội dung node và trạng thái đọc được rõ ràng.

Các phương án bố cục, màu cụ thể và tiêu chí nghiệm thu UI/UX sẽ được xác định khi lập kế hoạch Sprint 14; chưa chốt thiết kế chỉ từ hai ảnh này.

## 3. Use case và workflow làm việc xuyên suốt — ưu tiên rất cao

**Vấn đề chủ dự án nêu:** Các chức năng xét riêng lẻ ổn nhưng chưa tạo thành một workflow làm việc rõ ràng. Người dùng không thấy mối liên kết hoặc lối đi tự nhiên từ màn hình này sang màn hình khác; ngay trong một màn hình cũng khó hiểu mục đích, bước cần làm và bước tiếp theo. Vì vậy, nhìn vào sản phẩm chưa rõ có thể hoàn thành công việc từ đầu đến cuối như thế nào. Đây là vấn đề về trải nghiệm tổng thể, không chỉ là chỉnh màu hay bố cục của từng màn hình ở mục 2.

- **Ví dụ tại Notes — ảnh do chủ dự án cung cấp ở ý thứ ba:** Bên cạnh Note Composer và Assisted import, thao tác **“Capture exact spans”** lại nằm ở một nút riêng tại góc trên bên phải, không nổi bật và không làm rõ khi nào hoặc vì sao người dùng cần chọn nó. Người dùng có thể bỏ qua bước quan trọng này hoặc không hiểu các cách nhập/capture liên hệ với nhau thế nào.
- **Yêu cầu cho Sprint 14:** Xây dựng các use case thực tế và workflow end-to-end tương ứng; xác định mục tiêu người dùng, điểm bắt đầu, các bước và quyết định trong từng màn hình, cách chuyển tiếp giữa màn hình, trạng thái/đầu ra sau mỗi bước và cách tiếp tục tới kết quả cuối cùng. Dùng các workflow đó để tổ chức lại trải nghiệm và làm rõ hành động chính, thay vì chỉ cải thiện từng chức năng độc lập.
- **Đích kiểm chứng cần cụ thể hóa khi lập kế hoạch:** Người dùng phải nhận biết màn hình hiện tại dùng để làm gì, thao tác tiếp theo ở đâu và có thể đi trọn một use case qua các màn hình liên quan mà không phải tự đoán đường đi. Các use case cụ thể và cách kiểm chứng chưa được chốt chỉ từ ví dụ Notes này.

## 4. Đóng gói và khả năng chạy cho người dùng

**Yêu cầu của chủ dự án:** Không thể yêu cầu mọi người dùng tự cài Docker để chạy Projecta. Giao diện vẫn có thể mở bằng web trên `localhost`, nhưng cách cài đặt, khởi chạy và sử dụng phải thân thiện hơn, chẳng hạn qua một ứng dụng hoặc CLI phù hợp. Các service và dependency cần được đóng gói cẩn thận và kiểm chứng rằng hệ thống khởi chạy, hoạt động cùng nhau ổn định.

- Cần có một đường sử dụng dành cho người dùng **không đòi hỏi họ tự cài và vận hành Docker**; không đánh đồng quy trình chạy dành cho developer với trải nghiệm cài và chạy của người dùng.
- Việc đóng gói phải bao quát các service/phụ thuộc cần thiết cho workflow đã chọn, cách khởi động/dừng, cấu hình ban đầu và phản hồi rõ ràng khi có thành phần không sẵn sàng. Cần kiểm chứng trên môi trường cài đặt sạch và qua hành trình sử dụng thực tế, không chỉ xác nhận từng service chạy riêng lẻ.
- **Chưa chốt giải pháp:** Ứng dụng desktop, CLI, launcher hoặc phương án khác là các lựa chọn cần đánh giá; không mặc định phải triển khai đồng thời app và CLI, cũng không mặc định phải bỏ Compose khỏi quy trình phát triển/CI. Tài liệu kiến trúc hiện tại chọn Compose làm baseline cho phát triển, kiểm thử và triển khai sớm; yêu cầu mới đặt thêm ràng buộc cho đường phân phối tới người dùng, cần được thiết kế và quyết định riêng trước khi triển khai.

## 5. Khả năng chuyển giao dữ liệu giữa các máy

**Câu hỏi/yêu cầu của chủ dự án:** Thiết kế một định dạng xuất dữ liệu của Projecta có thể chuyển giao qua một kênh tệp như Google Drive, rồi được người dùng nhập lại — chấp nhận thao tác thủ công — vào Projecta trên máy khác. Mục tiêu là mang theo dữ liệu để tiếp tục sử dụng, không phụ thuộc vào cùng một máy hay một bản cài đặt; chưa yêu cầu tích hợp trực tiếp với Google Drive hoặc đồng bộ tự động.

- Sprint 14 cần xác định **phạm vi dữ liệu có thể chuyển giao** và định dạng export/import nhất quán, có khả năng nhận diện phiên bản. Cần xét dữ liệu dự án, nguồn/bằng chứng, tri thức và lịch sử/receipt liên quan giữa các lớp lưu trữ; không thể coi một bản xuất riêng từ graph hoặc database là đủ nếu sau khi nhập workflow không còn dùng được.
- Phải làm rõ quyền sở hữu/project scope, bảo vệ dữ liệu nhạy cảm và bí mật, kiểm tra tính toàn vẹn, phiên bản/migration và cách xử lý dữ liệu đã tồn tại trên máy đích trước khi triển khai. Không mặc định đóng gói credential, master key hoặc phiên đăng nhập vào tệp chuyển giao.
- **Đích kiểm chứng cần cụ thể hóa:** Xuất từ máy/bản cài đặt A, chuyển tệp qua một kênh thông thường, nhập thủ công trên máy/bản cài đặt B và kiểm tra dữ liệu cùng workflow thuộc phạm vi đã công bố vẫn xem và sử dụng được, không lẫn dự án hay làm mất provenance. Chưa chốt cấu trúc tệp, chính sách gộp/ghi đè, mức độ hỗ trợ xuyên phiên bản hoặc cơ chế đồng bộ.
