export default function Card({ children, className = "" }) {
  return (
    <div className={`bg-card border-2 border-ink shadow-carbon p-4 ${className}`}>
      {children}
    </div>
  );
}