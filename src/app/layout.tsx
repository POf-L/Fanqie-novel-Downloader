import './globals.css';
import { ReactNode } from 'react';
import Script from 'next/script';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Script
          id="orchids-browser-logs"
          src="https://slelguoygbfzlpylpxfs.supabase.co/storage/v1/object/public/scripts/orchids-browser-logs.js"
          strategy="afterInteractive"
          data-orchids-project-id="3e5ff5f9-456e-4bbb-b3f3-f6cbe1d904e4"
        />
        {children}
      </body>
    </html>
  );
}