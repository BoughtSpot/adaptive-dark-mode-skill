export function Header() {
  return (<header className="bg-white text-gray-900 border-b border-gray-200">
    <img src="/logo.png" alt="Acme logo" />
    <nav className="bg-white dark:bg-zinc-900 text-gray-800 dark:text-zinc-100">Shop</nav>
    <div className="dark:bg-black dark:text-white mix-blend-multiply">x</div>
    <div style={{ background: '#fff', color: '#222' }}>promo</div>
  </header>);
}
