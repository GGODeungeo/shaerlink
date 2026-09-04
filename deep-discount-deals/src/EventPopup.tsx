import { Analytics } from '@apps-in-toss/web-framework';
import { Close } from './components/icons';
import { useLockBodyScroll } from './useLockBodyScroll';

export function EventPopup({
  onOpenEvent,
  onClose,
}: {
  onOpenEvent: () => void;
  onClose: () => void;
}) {
  useLockBodyScroll();

  const handleOpen = () => {
    Analytics.click({ log_name: 'today_event_popup_click' });
    onOpenEvent();
  };

  return (
    <div className="event-popup-backdrop" onClick={onClose}>
      <div className="event-popup" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="event-popup__close" onClick={onClose} aria-label="닫기">
          <Close size={18} />
        </button>

        <button type="button" className="event-popup__card" onClick={handleOpen}>
          <span className="event-popup__emoji tf">🎉</span>
          <span className="event-popup__title">오늘의 특가 오픈 이벤트</span>
          <span className="event-popup__subtitle">평 많고 좋은 상품만 모았어요</span>
          <span className="event-popup__cta">지금 확인하기</span>
        </button>
      </div>
    </div>
  );
}
