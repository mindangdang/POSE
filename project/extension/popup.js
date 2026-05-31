async function sendMessageToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        return reject(new Error(chrome.runtime.lastError.message));
      }
      resolve(response);
    });
  });
}

async function ensureContentScript(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"]
    });
  } catch (err) {
    throw new Error("현재 탭에 콘텐츠 스크립트를 주입할 수 없습니다. 지원되는 웹 페이지에서 시도하세요.");
  }
}

document.getElementById('saveBtn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const saveBtn = document.getElementById('saveBtn');
  saveBtn.disabled = true;
  saveBtn.textContent = '처리 중...';
  
  try {
    if (!tab || !tab.id) {
      throw new Error('현재 활성 탭 정보를 가져올 수 없습니다.');
    }

    let response;
    try {
      response = await sendMessageToTab(tab.id, { type: "EXTRACT_PRODUCT" });
    } catch (sendError) {
      if (sendError.message.includes('Receiving end does not exist')) {
        await ensureContentScript(tab.id);
        response = await sendMessageToTab(tab.id, { type: "EXTRACT_PRODUCT" });
      } else {
        throw sendError;
      }
    }

    if (response && response.title && response.image_url) {
      const saveResponse = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ type: "SAVE_TO_SERVER", data: response }, (result) => {
          resolve(result);
        });
      });
      
      if (saveResponse && saveResponse.success) {
        saveBtn.textContent = '저장됨!';
        setTimeout(() => window.close(), 800);
      } else {
        throw new Error(saveResponse?.error || "상품 저장 실패");
      }
    } else {
      throw new Error("필수 상품 정보(제목, 이미지)가 없습니다.");
    }
  } catch (error) {
    console.error(error);
    saveBtn.textContent = '오류 발생';
    saveBtn.disabled = false;
    alert(`상품 정보를 추출할 수 없습니다: ${error.message}\n페이지가 완전히 로드되었는지 확인하세요.`);
  }
});