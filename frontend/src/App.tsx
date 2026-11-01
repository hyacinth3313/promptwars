import { FeedbackProvider } from './components/Feedback';
import { Link, Route, Routes } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import PlannerPage from './pages/PlannerPage';
export default function App() { return <FeedbackProvider><a href="#main-content" className="skip-link">Skip to content</a><div id="main-content" tabIndex={-1}><Routes><Route path="/" element={<LandingPage/>}/><Route path="/planner/:sessionId" element={<PlannerPage/>}/><Route path="*" element={<main className="page-container py-32"><h1 className="font-display text-4xl">A little off the beaten path.</h1><Link to="/" className="mt-6 inline-block underline">Let’s head home</Link></main>}/></Routes></div></FeedbackProvider>; }
