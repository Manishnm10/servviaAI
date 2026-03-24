import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'ServVia AI - Healthcare Intelligence',
  description: 'Next-Gen End-to-End Healthcare Application',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased text-foreground bg-background">
        {children}
      </body>
    </html>
  );
}
