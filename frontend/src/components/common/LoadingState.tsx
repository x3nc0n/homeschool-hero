export function LoadingState({ message = 'Loading…' }: { message?: string }) {
  return <div className="rounded-lg border bg-card p-8 text-center text-sm text-muted-foreground">{message}</div>
}
