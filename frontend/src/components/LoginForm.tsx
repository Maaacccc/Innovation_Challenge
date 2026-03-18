import { FormEvent, useState } from "react";

type LoginFormProps = {
  onSubmit: (email: string, password: string) => Promise<void>;
  error?: string | null;
};

const demoAccounts = [
  "reviewer.w@example.com -> patients A and C",
  "reviewer.m@example.com -> patient B",
  "caregiver.1@example.com -> patients A and B",
  "caregiver.2@example.com -> patient C",
  "patient.a@example.com",
  "patient.b@example.com",
  "patient.c@example.com",
];

export function LoginForm({ onSubmit, error }: LoginFormProps) {
  const [email, setEmail] = useState("reviewer.w@example.com");
  const [password, setPassword] = useState("demo1234");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    try {
      await onSubmit(email, password);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="login-shell">
      <div className="login-copy">
        <p className="eyebrow">Production-style prototype</p>
        <h1>Human role workspaces on top of a backend care-team of agents.</h1>
        <p className="lede">
          Agents do not log in. They run inside the backend orchestration layer. Sign in with human care-team roles
          only. This demo now uses three patients, two caregivers, and two reviewers with scoped patient assignments.
        </p>
        <div className="demo-card">
          <strong>Human demo accounts</strong>
          <ul>
            {demoAccounts.map((account) => (
              <li key={account}>{account}</li>
            ))}
          </ul>
          <p>Password: <code>demo1234</code></p>
        </div>
      </div>
      <form className="login-panel" onSubmit={handleSubmit}>
        <label>
          Email
          <input value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label>
          Password
          <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {error ? <p className="error-text">{error}</p> : null}
        <button type="submit" disabled={loading}>
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </section>
  );
}
