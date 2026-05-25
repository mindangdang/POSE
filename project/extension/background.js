// API 엔드포인트
const API_URL = "http://localhost:8000/api/import-product";
const TIMEOUT_MS = 8000; // 8초 타임아웃

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "SAVE_TO_SERVER") {
    saveProduct(request.data).catch(e => {
      console.error("저장 실패:", e);
    });
  }
  return true;
});

/**
 * 상품 데이터를 백엔드 서버로 POST 전송
 */
async function saveProduct(productData) {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);
    
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(productData),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (response.ok) {
      chrome.notifications.create({
        type: "basic",
        title: "VibeSearch",
        message: "상품이 성공적으로 저장되었습니다!",
        priority: 1
      });
      console.log("상품 저장 성공:", productData.title);
    } else {
      const errorText = await response.text();
      console.error(`서버 오류 [${response.status}]:`, errorText);
      
      if (response.status === 400) {
        chrome.notifications.create({
          type: "basic",
          title: "VibeSearch",
          message: "유효하지 않은 상품 정보입니다.",
          priority: 1
        });
      } else if (response.status >= 500) {
        chrome.notifications.create({
          type: "basic",
          title: "VibeSearch",
          message: "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
          priority: 1
        });
      }
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      console.error("요청 타임아웃");
      chrome.notifications.create({
        type: "basic",
        title: "VibeSearch",
        message: "요청 타임아웃. 서버 연결을 확인해주세요.",
        priority: 1
      });
    } else {
      console.error("요청 실패:", e);
      chrome.notifications.create({
        type: "basic",
        title: "VibeSearch",
        message: "서버 연결에 실패했습니다.",
        priority: 1
      });
    }
  }
}