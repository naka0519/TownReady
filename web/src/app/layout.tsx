export const metadata = {
  title: 'TownReady',
  description: 'Minimal web for TownReady',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body style={{ fontFamily: 'system-ui, sans-serif', padding: 16 }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ margin: 0 }}>TownReady</h2>
          <a href="/" style={{ marginLeft: 'auto' }}>Home</a>
        </header>
        <main style={{ marginTop: 12 }}>{children}</main>
      </body>
    </html>
  );
}

