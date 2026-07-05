export type Shop = {
  name: string;
  url: string;
  desc: string;
};

export type SearchMode = "digging" | "ai";

export type DetailedSearchQuery = {
  mood: string;
  color: string;
  fit: string;
  category: string;
  brand: string;
};

export const DEFAULT_DETAILED_SEARCH_QUERY: DetailedSearchQuery = {
  mood: "",
  color: "",
  fit: "",
  category: "",
  brand: "",
};

const SHOP_STORAGE_KEY = 'user_shops';

const SUGGESTION_POOL = [
  "빈티지 리바이스",
  "폴로 카라티",
  "아르마니 익스체인지",
  "슬림핏 반팔",
  "유니폼",
  "아크테릭스 바람막이",
  "와이드 팬츠",
  "디스트로이드 데님",
  "빈티지 돌체 앤 가바나",
  "테크웨어",
  "웨스턴 셔츠",
  "그런지 팬츠",
  "올드머니 룩",
  "가죽 자켓",
  "포엣코어",
  "Y2K",
  "버버리 트렌치 코트",
  "헤비 스웨트셔츠",
  "팀버랜드 부츠",
  "펜던트 목걸이"
];

const SELECT_SHOPS = [
  { name: "FRUITS FAMILY", desc: "감도높은 빈티지/세컨핸드 매물 거래용", url: "https://fruitsfamily.com" },
  { name: "FETCHING", desc: "전 세계 럭셔리 편집샵 아이템 비교 직구", url: "https://fetching.co.kr" },
  { name: "EMPTY", desc: "무신사가 제안하는 실험적 디자이너 브랜드", url: "https://empty.seoul.kr" },
  { name: "WORKSOUT", desc: "하이엔드 스트릿웨어와 라이프스타일 셀렉샵", url: "https://worksout.co.kr" },
  { name: "8DIVISION", desc: "남성 헤리티지 및 컨템포러리 셀렉샵", url: "https://8division.com" },
  { name: "IAMSHOP", desc: "고감도 컨템포러리 브랜드 및 워크웨어 큐레이션", url: "https://iamshop-online.com" },
  { name: "THE BOUNCE", desc: "국내외 인기 스트릿 브랜드를 모은 멀티샵", url: "https://thebounce.co.kr" },
  { name: "THE X SHOP", desc: "스트릿 컬처와 스케이트보드 편집 매장", url: "https://thexshop.co.kr" },
  { name: "COLLECTIV", desc: "세컨핸드 패션의 새로운 가치를 제안하는 플랫폼", url: "https://collectiv.kr" },
  { name: "KREAM", desc: "한정판 스니커즈와 럭셔리 아이템 거래 플랫폼", url: "https://kream.co.kr" },
  { name: "MUSINSA", desc: "국내 최대 패션 스토어 및 트렌드 큐레이션", url: "https://musinsa.com" },
  { name: "EQL", desc: "한섬에서 제안하는 감각적인 라이프스타일 셀렉샵", url: "https://eqlstore.com" },
  { name: "29CM", desc: "감도깊은 취향 셀렉트샵", url: "https://29cm.co.kr" },
  { name: "Bunjang", desc: "브랜드 중고거래 플랫폼", url: "https://bunjang.co.kr" },
  { name: "Danggeun Market", desc: "지역 기반 중고거래 플랫폼", url: "https://www.daangn.com" },
  { name: "Joonggonara", desc: "중고나라 커뮤니티 기반 중고거래 플랫폼", url: "https://www.joongna.com" },
  { name: "ZARA", desc: "글로벌 패션 브랜드, 트렌디한 아이템 다수 보유", url: "https://www.zara.com" }
];

export function getInitialShops() {
  const saved = localStorage.getItem(SHOP_STORAGE_KEY);
  return saved ? JSON.parse(saved) as Shop[] : SELECT_SHOPS;
}

export function saveShops(shops: Shop[]) {
  localStorage.setItem(SHOP_STORAGE_KEY, JSON.stringify(shops));
}

export function getRandomSuggestions(count = 6) {
  return [...SUGGESTION_POOL].sort(() => 0.5 - Math.random()).slice(0, count);
}
