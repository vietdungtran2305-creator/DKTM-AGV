AGV WEB V2 - GIAO DIEN GIAM SAT KHO HANG

CAC FILE
- server.py: Flask API + SQLite, chay tren laptop.
- templates/index.html: giao dien dashboard.
- static/style.css: giao dien mau sac, responsive cho dien thoai/laptop.
- static/app.js: cap nhat trang thai, can nang, kho va lich su.
- wifi_client.py: module MicroPython da co tu ban V1; chua ghep vao chuong trinh xe chinh.

CHAY TREN LAPTOP
1. Sao luu thu muc agv_web_v1 cu truoc khi thay file.
2. Mo CMD tai thu muc chua server.py.
3. Cai Flask neu may chua co: py -m pip install flask
4. Chay: py server.py
5. Mo: http://127.0.0.1:5000
6. Thiet bi khac trong cung mang LAN truy cap laptop qua http://IP_LAPTOP:5000.

CAC CHUC NANG
- Bo khoang cach vat can khoi giao dien.
- Hien thi trang thai may chu rieng voi trang thai ket noi ESP32.
- Hien thi khoi luong va loai hang moi nhat ma ESP32 gui len.
- Quy uoc kho co dinh: KHO1 chi nhan LIGHT (hang nhe), KHO2 chi nhan HEAVY (hang nang); API tu choi ban ghi sai kho.
- Khi status la OBSTACLE_STOP hoac WAIT_RESUME, hien thi canh bao va yeu cau nguoi van hanh xac nhan duong di da thong.
- API resume chi nhan yeu cau khi xe dang bao dung do vat can va du lieu telemetry con moi (15 giay). Day la lenh yeu cau, KHONG phai lenh bo qua cam bien; ESP32 phai tu kiem tra an toan truoc khi chay dong co.
- Lich su giao hang luu thoi gian, trip_id, kho, loai hang, can truoc giao va can sau do.
- Moi trip_id chi tang ton kho mot lan nhờ UNIQUE PRIMARY KEY va INSERT OR IGNORE trong SQLite.
- SQLite luu trong agv_data.sqlite3 cung thu muc server.py; file nay duoc tao khi khoi dong server lan dau.

QUAN TRONG
- Website hien thi du lieu ma ESP32 gui len; no khong tu can duoc hang va khong tu phat hien vat can.
- Can phan ESP32 gui telemetry dinh ky de website biet xe con ket noi. Neu qua 15 giay khong co telemetry, website hien thi xe chua ket noi va khoa nut yeu cau chay tiep.
- Muon nut xac nhan hoat dong thuc te, chuong trinh MicroPython tren ESP32 phai goi wifi_client.get_command() dinh ky va xu ly lenh 'resume' an toan. Chi sua website/server chua lam xe tu dung/chay tiep.
- Khi giao hang, ESP32 can gui POST /api/delivery voi trip_id duy nhat, warehouse la KHO1/KHO2, load_level, weight_before va weight_after. Khong tao lai trip_id cho cac lan retry cua cung mot chuyen.
- Truoc khi thay server.py, hay giu lai ban sao; file database agv_data.sqlite3 cu neu co phai duoc giu de khong mat lich su kho.
