import Header from "@/components/Header";
import Hero from "@/components/Hero";
import Dashboard from "@/components/Dashboard";

export default function Home() {
  return (
    <>
      <Header />
      <main className="mx-auto max-w-[82rem] space-y-5 px-4 py-6 sm:px-6">
        <Hero />
        <Dashboard />
      </main>
    </>
  );
}
