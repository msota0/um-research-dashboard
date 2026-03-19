import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'UM Research Dashboard — University of Mississippi',
  description: 'Research analytics for the University of Mississippi (Oxford, MS). Data from OpenAlex and Dimensions AI.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
