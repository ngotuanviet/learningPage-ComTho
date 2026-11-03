/**
 * Nhận dữ liệu form đăng ký tư vấn hợp tác và ghi vào Google Sheet.
 *
 * Cách dùng:
 * 1. Tạo Google Sheet mới -> Extensions (Tiện ích mở rộng) -> Apps Script.
 * 2. Dán toàn bộ file này vào, lưu.
 * 3. (Tùy chọn) Điền NOTIFY_EMAIL để nhận email mỗi khi có đăng ký mới.
 * 4. Deploy -> New deployment -> loại "Web app".
 *    Execute as: Me | Who has access: Anyone.
 * 5. Copy URL (kết thúc bằng /exec) dán vào SHEET_ENDPOINT trong js/franchise.js.
 * Mỗi lần sửa script phải Deploy phiên bản mới thì URL mới có hiệu lực.
 *
 * Cột "Trạng thái" mặc định là "Mới"; bộ phận kinh doanh đổi tay thành
 * "Đã liên hệ", "Đang tư vấn", "Đã ký"... để theo dõi xử lý.
 */
const SHEET_NAME = 'Đăng ký hợp tác';
const NOTIFY_EMAIL = ''; // ví dụ: 'kinhdoanh@ten-mien.vn'; để trống nếu không cần
const HEADERS = ['Thời gian', 'Họ tên', 'Số điện thoại', 'Email', 'Tỉnh/Thành phố', 'Hình thức hợp tác',
                 'Ngân sách', 'Nội dung cần tư vấn', 'Trạng thái', 'Nguồn trang'];

function doPost(e) {
  const p = (e && e.parameter) || {};
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName(SHEET_NAME);
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(HEADERS);
      sheet.setFrozenRows(1);
    }
    const row = sheet.getLastRow() + 1;
    sheet.getRange(row, 3).setNumberFormat('@'); // giữ số 0 đầu của SĐT
    sheet.getRange(row, 1, 1, HEADERS.length).setValues([[
      new Date(), p.name || '', p.phone || '', p.email || '', p.area || '', p.model || '',
      p.budget || '', p.note || '', 'Mới', p.source || ''
    ]]);

    if (NOTIFY_EMAIL) {
      MailApp.sendEmail(NOTIFY_EMAIL, 'Đăng ký tư vấn hợp tác mới: ' + (p.name || ''),
        'Họ tên: ' + (p.name || '') + '\nSĐT: ' + (p.phone || '') + '\nEmail: ' + (p.email || '') +
        '\nKhu vực: ' + (p.area || '') + '\nHình thức: ' + (p.model || '') +
        '\nNgân sách: ' + (p.budget || '') + '\nNội dung: ' + (p.note || ''));
    }
    return ContentService.createTextOutput('ok');
  } finally {
    lock.releaseLock();
  }
}

function doGet() {
  return ContentService.createTextOutput('Partnership form endpoint is running.');
}
