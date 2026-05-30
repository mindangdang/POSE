// API 엔드포인트
// 코드스페이스의 Ports 탭에서 8000번 포트의 'Forwarded Address'를 복사하여 붙여넣으세요.
const API_URL = "https://ideal-carnival-qvqr6x75gx54c96g7-8000.app.github.dev/api/import-product";
const TIMEOUT_MS = 8000; // 8초 타임아웃

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "SAVE_TO_SERVER") {
    saveProduct(request.data)
      .then((res) => {
        sendResponse({ success: true, data: res });
      })
      .catch(e => {
        console.error("저장 실패:", e);
        sendResponse({ success: false, error: e.message || "알 수 없는 오류 발생" });
      });
    return true; // 비동기 응답 활성화
  }

  if (request.type === "SYNC_TOKEN") {
    chrome.storage.local.set({ access_token: request.token });
    return true;
  }
});

/**
 * 상품 데이터를 백엔드 서버로 POST 전송
 */
async function saveProduct(productData) {
  try {
    const { access_token } = await chrome.storage.local.get("access_token");
    if (!access_token) {
      throw new Error("로그인이 필요합니다. POSE 웹사이트에서 로그인 후 다시 시도해주세요.");
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);
    
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${access_token}`
      },
      body: JSON.stringify(productData),
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    
    if (response.ok) {
      chrome.notifications.create({
        type: "basic",
        iconUrl: "project/extension/icon.png",
        title: "VibeSearch",
        message: "상품이 성공적으로 저장되었습니다!",
        priority: 1
      });
      console.log("상품 저장 성공:", productData.title);
      return await response.json();
    } else {
      const errorText = await response.text();
      let errorMessage = `서버 오류 [${response.status}]`;
      try { errorMessage = JSON.parse(errorText).detail || errorMessage; } catch(e) {}
      
      console.error(errorMessage);
      if (response.status === 400) {
        chrome.notifications.create({
          type: "basic",
          iconUrl: "project/extension/icon.png",
          title: "VibeSearch",
          message: "유효하지 않은 상품 정보입니다.",
          priority: 1
        });
      } else if (response.status >= 500) {
        chrome.notifications.create({
          type: "basic",
          iconUrl: "project/extension/icon.png",
          title: "VibeSearch",
          message: "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
          priority: 1
        });
      }
      throw new Error(errorMessage);
    }
  } catch (e) {
    if (e.name === 'AbortError') {
      console.error("요청 타임아웃");
      chrome.notifications.create({
        type: "basic",
        iconUrl: "project/extension/icon.png",
        title: "VibeSearch",
        message: "요청 타임아웃. 서버 연결을 확인해주세요.",
        priority: 1
      });
    } else {
      console.error("요청 실패:", e);
      chrome.notifications.create({
        type: "basic",
        iconUrl: "project/extension/icon.png",
        title: "VibeSearch",
        message: "서버 연결에 실패했습니다.",
        priority: 1
      });
      throw new Error("서버 연결에 실패했습니다. 백엔드 서버가 켜져 있는지 확인하세요.");
    }
    throw e;
  }
}