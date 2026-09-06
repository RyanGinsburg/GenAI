// variant="inline": a small spinner + label, for a single wait (a chat
// turn). variant="bar": a slim indeterminate progress bar, for a longer
// transition (computing matches after the interview ends).
export default function LoadingIndicator({ label, variant = 'inline' }) {
  if (variant === 'bar') {
    return (
      <div className="loading-bar-wrap">
        <div className="progress-bar">
          <div className="progress-bar__fill" />
        </div>
        {label && <p className="loading-bar-wrap__label">{label}</p>}
      </div>
    )
  }

  return (
    <div className="loading-inline">
      <span className="spinner" aria-hidden="true" />
      {label && <span>{label}</span>}
    </div>
  )
}
