import { useEffect } from 'react';

/**
 * 바텀시트/팝업이 배경 위에 떠 있을 때, 그 위에서 스크롤하면 뒤에 깔린 메인
 * 화면이 같이 움직여 보이는 문제를 막는다 - 열려있는 동안 body 스크롤을
 * 잠그고, 닫히면 원래 값으로 복원한다.
 */
export function useLockBodyScroll() {
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);
}
