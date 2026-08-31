export function CategoryNav({ categories }: { categories: string[] }) {
  const handleClick = (category: string) => {
    document.getElementById(`category-${category}`)?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    });
  };

  return (
    <nav className="category-nav" aria-label="카테고리 바로가기">
      {categories.map((category) => (
        <button
          key={category}
          type="button"
          className="category-nav__chip"
          onClick={() => handleClick(category)}
        >
          {category}
        </button>
      ))}
    </nav>
  );
}
