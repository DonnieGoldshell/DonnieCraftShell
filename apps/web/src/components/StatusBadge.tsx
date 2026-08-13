import { displayStatus, statusTone } from "@/lib/format";

type Props = {
  value: string | null | undefined;
};

export function StatusBadge({ value }: Props) {
  return <span className={`status status-${statusTone(value)}`}>{displayStatus(value)}</span>;
}
