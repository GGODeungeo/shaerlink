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
          {category}
        </button>
      ))}
    </nav>
  );
}
