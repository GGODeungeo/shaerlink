import { useState } from 'react';
import { getAnonKey } from './trackedLink';

const REVIEW_URL = 'https://shaerlink.vercel.app/api/review';
const MIN_LENGTH = 10;

export function ReviewPromptCard({ onSubmitted }: { onSubmitted: () => void }) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(false);

  const handleSubmit = async () => {
    const anonKey = await getAnonKey();
    if (!anonKey) return;

    setSubmitting(true);
    setError(false);
    try {
      const res = await fetch(REVIEW_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ anonKey, text }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onSubmitted();
    } catch {
      setError(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="review-prompt-card">
      <span className="review-prompt-card__title">숨은특가 어때요? 한 줄 남기고 20원 받기</span>
      <textarea
        className="review-prompt-card__textarea"
        placeholder="어떤 점이 좋았는지, 아쉬운지 알려주세요 (10자 이상)"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      {error && <span className="review-prompt-card__error">제출에 실패했어요. 다시 시도해주세요.</span>}
      <button
        type="button"
        className="review-prompt-card__submit"
        disabled={text.trim().length < MIN_LENGTH || submitting}
        onClick={handleSubmit}
      >
        {submitting ? '보내는 중...' : '보내고 20원 받기'}
      </button>
    </div>
  );
}
