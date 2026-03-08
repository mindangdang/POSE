from Rapid_api_crawler import Rapid_crawler
import requests
import json
import re
import os
from image_ocr_llm import extract_fact_and_vibe
from instagram_crawler import download_images # 다운로드 함수는 그대로 씁니다!
from insert_db import insert_items_to_db


def main():
    test_url = "https://www.instagram.com/p/DThhqQAjxcW/?utm_source=ig_web_copy_link"
    
    print("🚀 [Step 1] API 기반 인스타그램 데이터 수집 시작...")
    crawl_result = Rapid_crawler(test_url)

    if crawl_result.get("error"):
        print(f"❌ 크롤링 실패: {crawl_result['error']}")
        return

    caption_preview = crawl_result['caption'][:20] if crawl_result['caption'] else "없음"
    print(f"\n✅ [Step 1 완료] 수집 성공! (이미지 {len(crawl_result['image_urls'])}장, 캡션: {caption_preview}...)") 

    # 2️⃣ 이미지 다운로드
    if not crawl_result["image_urls"]:
        print("⚠️ 수집된 이미지가 없습니다.")
        return

    print("\n🚀 [Step 2] 이미지 다운로드 시작...")
    downloaded_files = download_images(crawl_result["image_urls"], save_dir="insta_vibes") 

    # 3️⃣ AI 분석 실행 
    if downloaded_files:
        print("\n🚀 [Step 3] AI 데이터 추출 시작...")
        
        ai_result = extract_fact_and_vibe(
            image_paths=downloaded_files, 
            caption=crawl_result["caption"],  
            hashtags=crawl_result["hashtags"] 
        )
        
        print("\n" + "="*50)
        print("🎯 [최종 DB 적재용 AI 분석 결과]")
        print("="*50)
        print(json.dumps(ai_result, ensure_ascii=False, indent=2))
        print("="*50)

        # 4️⃣ DB 적재
        print("\n🚀 [Step 4] Neon DB 데이터 적재 시작...")
        extracted_items = ai_result.get("extracted_items", [])
        
        if extracted_items:
            test_user_id = "mindangdang_01" 
            insert_items_to_db(test_user_id, test_url, extracted_items)
            print("\n🎉 [End-to-End 성공] 데이터 수집부터 DB 적재까지 완벽하게 끝났습니다!")
        else:
            print("⚠️ DB에 적재할 유의미한 아이템이 분석되지 않았습니다.")

if __name__ == "__main__":
    main()