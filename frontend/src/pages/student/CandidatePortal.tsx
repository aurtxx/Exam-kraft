import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import studentExamApi, { CandidateExamination } from '../../services/studentExamApi';

export default function CandidatePortal() {
  const { user, logout } = useAuth();
  const [exams, setExams] = useState<CandidateExamination[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    studentExamApi.listExaminations().then(
      (items) => { if (active) setExams(items); },
      () => { if (active) setFailed(true); },
    );
    return () => { active = false; };
  }, []);

  return (
    <main className="mx-auto max-w-3xl space-y-5 p-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">My Examinations</h1>
          <p className="text-sm text-slate-600">{user?.profile?.full_name || user?.username}</p>
        </div>
        <button className="text-sm font-semibold text-primary-700" onClick={() => void logout()}>Sign out</button>
      </header>
      {failed && <p role="alert">Could not load examinations. Refresh the page to try again.</p>}
      {!failed && exams === null && <p role="status">Loading examinations…</p>}
      {exams?.length === 0 && <p>No current or upcoming examinations.</p>}
      {exams?.map((exam) => (
        <article key={exam.id} className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="font-semibold text-slate-900">{exam.name}</h2>
          <p className="my-2 text-sm text-slate-600">
            {exam.duration_minutes} minutes
            {exam.start_window && <> · Opens {new Date(exam.start_window).toLocaleString()}</>}
          </p>
          <Link className="font-semibold text-primary-700" to={`/student/exam/${exam.id}/lobby`}>
            Open lobby
          </Link>
        </article>
      ))}
    </main>
  );
}
