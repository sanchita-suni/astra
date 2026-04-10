import { useEffect, useState } from "react";

interface Item {
  id: number;
  name: string;
}

export default function App() {
  const [items, setItems] = useState<Item[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/items")
      .then((r) => r.json())
      .then(setItems)
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: "2rem", maxWidth: 640 }}>
      <h1>Hello, hackathon.</h1>
      <p>Edit <code>src/App.tsx</code> to start. Read <code>BRIEF.md</code> for what you&apos;re building.</p>
      {error ? <p style={{ color: "crimson" }}>{error}</p> : (
        <ul>
          {items.map((it) => (
            <li key={it.id}>{it.name}</li>
          ))}
        </ul>
      )}
    </main>
  );
}
