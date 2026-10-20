export const STARTER_PROMPTS = [
  'What is agentic AI?',
  'Explain Amazon Bedrock AgentCore',
  'Show a Strands Agents example',
  'Describe the target architecture',
];

interface Props {
  onSelect: (prompt: string) => void;
  disabled?: boolean;
  prompts?: string[];
}

export function SuggestedPrompts({ onSelect, disabled, prompts = STARTER_PROMPTS }: Props) {
  return (
    <ul className="grid w-full max-w-xl gap-2 sm:grid-cols-2" aria-label="Suggested prompts">
      {prompts.map((p) => (
        <li key={p}>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onSelect(p)}
            className="w-full rounded-xl border border-line bg-surface px-4 py-3 text-left text-sm transition hover:border-accent/50 hover:bg-surface-2 disabled:opacity-50"
          >
            {p}
          </button>
        </li>
      ))}
    </ul>
  );
}
