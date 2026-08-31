import { ChevronRight } from './components/icons';

export function CategoryNav({
  categories,
  onSelect,
}: {
  categories: string[];
  onSelect: (category: string) => void;
}) {
  return (
    <nav className="category-list" aria-label="카테고리">
      {categories.map((category) => (
        <button
          key={category}
          type="button"
          className="category-list__item"
          onClick={() => onSelect(category)}
        >
          {category}
          <ChevronRight size={16} />
        </button>
      ))}
    </nav>
  );
}
