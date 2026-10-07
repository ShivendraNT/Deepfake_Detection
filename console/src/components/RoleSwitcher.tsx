// T06: demo role switcher. The identity is sent as X-Demo-User / X-Demo-Role headers.
import { DEMO_USERS } from "../api";
import type { DemoUser } from "../types";

interface RoleSwitcherProps {
  user: DemoUser;
  onChange: (u: DemoUser) => void;
}

export function RoleSwitcher({ user, onChange }: RoleSwitcherProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
      <span>Signed in as</span>
      <select
        data-testid="role-switcher"
        className="rounded border border-slate-300 bg-white px-2 py-1 text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
        value={user.employeeId}
        onChange={(e) => {
          const found = DEMO_USERS.find((d) => d.user.employeeId === e.target.value);
          if (found) onChange(found.user);
        }}
      >
        {DEMO_USERS.map((d) => (
          <option key={d.user.employeeId} value={d.user.employeeId}>
            {d.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export default RoleSwitcher;
