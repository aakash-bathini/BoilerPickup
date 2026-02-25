import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';
import Navbar from '@/components/Navbar';
import CoachPete from '@/components/CoachPete';

export const metadata: Metadata = {
  title: 'Boiler Pickup | AI-Powered Basketball Matchmaking',
  description: 'Find skill-matched pickup basketball games at Purdue CoRec. AI-powered team balancing, stat tracking, and player ratings.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-dark-500">
        <AuthProvider>
          <Navbar />
          <main className="min-h-screen bg-dark-500">
            {children}
          </main>
          <CoachPete />
        </AuthProvider>
      </body>
    </html>
  );
}
