import { ThemeProvider } from 'next-themes';
export default function RootLayout({ children }) {
  return (<html lang="en" suppressHydrationWarning><body>
    <ThemeProvider attribute="class" defaultTheme="light">{children}</ThemeProvider>
  </body></html>);
}
