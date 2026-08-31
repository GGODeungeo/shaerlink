const CATEGORY_EMOJI: Record<string, string> = {
  '가구/홈데코': '🛋️',
  '가전/디지털': '📱',
  '문구/오피스': '📎',
  '반려/애완용품': '🐾',
  '뷰티': '💄',
  '생활용품': '🧻',
  '스포츠/레져': '⚽',
  '식품': '🍎',
  '여행/취미': '✈️',
  '완구/취미': '🧸',
  '음반/DVD': '🎵',
  '자동차용품': '🚗',
  '주방용품': '🍳',
  '출산/유아동': '🍼',
  '패션의류잡화': '👕',
};

export function CategoryNav({
  categories,
  selected,
  onSelect,
}: {
  categories: string[];
  selected: string;
  onSelect: (category: string) => void;
}) {
  return (
    <nav className="sidebar" aria-label="카테고리">
      {categories.map((category) => (
        <button
          key={category}
          type="button"
          className={
            category === selected ? 'sidebar__item sidebar__item--active' : 'sidebar__item'
          }
          onClick={() => onSelect(category)}
        >
          <span className="tf sidebar__item-emoji" aria-hidden="true">
            {CATEGORY_EMOJI[category] ?? '🛍️'}
          </span>
          {category}
        </button>
      ))}
    </nav>
  );
}
