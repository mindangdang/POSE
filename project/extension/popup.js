document.getElementById('saveBtn').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const saveBtn = document.getElementById('saveBtn');
  saveBtn.disabled = true;
  saveBtn.textContent = '처리 중...';
  
  try {
    const response = await chrome.tabs.sendMessage(tab.id, { type: "EXTRACT_PRODUCT" });
    if (response) {
      chrome.runtime.sendMessage({ type: "SAVE_TO_SERVER", data: response });
      saveBtn.textContent = '저장됨!';
      setTimeout(() => window.close(), 800);
    } else {
      throw new Error("상품 정보 추출 실패");
    }
  } catch (error) {
    console.error(error);
    saveBtn.textContent = '오류 발생';
    saveBtn.disabled = false;
    alert("상품 정보를 추출할 수 없습니다. 페이지가 완전히 로드되었는지 확인하세요.");
  }
});