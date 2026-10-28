import React, { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { studentApi, type FacultyMember } from '../../api/students';
import type { Student } from '../../types';
import { RiskBadge } from '../../components/common/RiskBadge';
import { SkeletonTable } from '../../components/common/Skeleton';
import { ImportModal } from '../../components/students/ImportModal';
import { CreateStudentModal } from '../../components/students/CreateStudentModal';
import { useAuth } from '../../context/AuthContext';
import {
  Search,
  FileSpreadsheet,
  ChevronLeft,
  ChevronRight,
  GraduationCap,
  UserPlus,
} from 'lucide-react';

export const StudentsPage: React.FC = () => {
  const { hasRole } = useAuth();

  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [department, setDepartment] = useState<string>('');
  const [semester, setSemester] = useState<string>('');
  const [level, setLevel] = useState<string>('');
  const [selectedTeacher, setSelectedTeacher] = useState<string>('');
  const [faculty, setFaculty] = useState<FacultyMember[]>([]);
  const [facultyMap, setFacultyMap] = useState<Record<string, FacultyMember>>({});
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [cursorHistory, setCursorHistory] = useState<(string | undefined)[]>([]);
  const [importModalOpen, setImportModalOpen] = useState<boolean>(false);
  const [createModalOpen, setCreateModalOpen] = useState<boolean>(false);

  useEffect(() => {
    studentApi
      .listFaculty()
      .then((data) => {
        setFaculty(data);
        const map: Record<string, FacultyMember> = {};
        data.forEach((f) => {
          map[f.id] = f;
        });
        setFacultyMap(map);
      })
      .catch((err) => console.error('Failed to load faculty', err));
  }, []);

  const fetchStudents = useCallback(async (cursorVal?: string) => {
    setLoading(true);
    try {
      const res = await studentApi.listStudents({
        cursor: cursorVal,
        limit: 15,
        search: search.trim() || undefined,
        department: department || undefined,
        semester: semester ? parseInt(semester, 10) : undefined,
        level: level || undefined,
        teacher_id: selectedTeacher || undefined,
      });

      setStudents(res.items);
      setNextCursor(res.next_cursor);
      setHasMore(res.has_more);
    } catch (err) {
      console.error('Failed to fetch students', err);
    } finally {
      setLoading(false);
    }
  }, [department, level, search, semester, selectedTeacher]);

  useEffect(() => {
    setCursorHistory([]);
    fetchStudents(undefined);
  }, [fetchStudents]);

  const handleNextPage = () => {
    if (nextCursor) {
      setCursorHistory((prev) => [...prev, nextCursor]);
      fetchStudents(nextCursor);
    }
  };

  const handlePrevPage = () => {
    if (cursorHistory.length > 0) {
      const newHistory = [...cursorHistory];
      newHistory.pop(); // Remove current
      const prev = newHistory[newHistory.length - 1];
      setCursorHistory(newHistory);
      fetchStudents(prev);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-up">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-sand-200 dark:border-charcoal-800">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-ink-900 dark:text-sand-100">
            Student Cohort Directory
          </h1>
          <p className="text-xs sm:text-sm text-ink-500 dark:text-sand-400 mt-1">
            Search, filter, and inspect student risk profiles and academic trajectories.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          {hasRole(['admin', 'hod', 'teacher']) && (
            <button
              onClick={() => setCreateModalOpen(true)}
              className="inline-flex items-center px-4 py-2 rounded-xl bg-clay-500 hover:bg-clay-600 text-white text-xs font-semibold shadow-soft card-lift transition-all"
            >
              <UserPlus className="w-4 h-4 mr-1.5" /> Add Student
            </button>
          )}

          {hasRole(['admin', 'hod']) && (
            <button
              onClick={() => setImportModalOpen(true)}
              className="inline-flex items-center px-4 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-800 hover:bg-sand-50 dark:hover:bg-charcoal-750 text-ink-700 dark:text-sand-300 text-xs font-semibold shadow-soft transition-all"
            >
              <FileSpreadsheet className="w-4 h-4 mr-1.5" /> Bulk Import CSV
            </button>
          )}
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 p-4 shadow-soft space-y-3">
        <div className={`grid grid-cols-1 sm:grid-cols-2 ${hasRole(['admin', 'hod']) ? 'lg:grid-cols-5' : 'lg:grid-cols-4'} gap-3`}>
          {/* Search */}
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-400">
              <Search className="w-4 h-4" />
            </div>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by student name or ERP ID..."
              className="w-full pl-9 pr-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
            />
          </div>

          {/* Department Filter */}
          <select
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
            className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          >
            <option value="">All Departments</option>
            <option value="Computer Science">Computer Science</option>
            <option value="Electronics">Electronics</option>
            <option value="Mechanical">Mechanical</option>
            <option value="Civil">Civil</option>
          </select>

          {/* Semester Filter */}
          <select
            value={semester}
            onChange={(e) => setSemester(e.target.value)}
            className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          >
            <option value="">All Semesters</option>
            {Array.from({ length: 8 }).map((_, i) => (
              <option key={i + 1} value={i + 1}>
                Semester {i + 1}
              </option>
            ))}
          </select>

          {/* Risk Level Filter */}
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
          >
            <option value="">All Risk Tiers</option>
            <option value="High">High Risk</option>
            <option value="Medium">Medium Risk</option>
            <option value="Low">Low Risk</option>
            <option value="Insufficient Data">Insufficient Data</option>
          </select>

          {/* Faculty / Mentor Filter (Admin & HOD only) */}
          {hasRole(['admin', 'hod']) && (
            <select
              value={selectedTeacher}
              onChange={(e) => setSelectedTeacher(e.target.value)}
              className="px-3 py-2 rounded-xl border border-sand-300 dark:border-charcoal-700 bg-white dark:bg-charcoal-850 text-xs text-ink-900 dark:text-sand-100 focus:outline-none focus:ring-2 focus:ring-clay-400/50"
            >
              <option value="">All Faculty Mentors</option>
              {faculty.map((f) => (
                <option key={f.id} value={f.id}>
                  👨‍🏫 {f.name} ({f.department || 'Faculty'})
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Student Table */}
      <div className="bg-white dark:bg-charcoal-800 rounded-2xl border border-sand-200 dark:border-charcoal-700 shadow-soft overflow-hidden">
        {loading ? (
          <SkeletonTable rows={8} />
        ) : students.length === 0 ? (
          <div className="p-12 text-center text-xs text-ink-500 dark:text-sand-400 space-y-2">
            <GraduationCap className="w-8 h-8 mx-auto text-sand-400" />
            <p className="font-semibold text-sm text-ink-900 dark:text-sand-100">
              No students found matching your criteria.
            </p>
            <p>Try refining your search query or reset the applied filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-cream-50 dark:bg-charcoal-750 text-ink-600 dark:text-sand-400 uppercase font-semibold">
                <tr>
                  <th className="px-5 py-3.5">Student</th>
                  <th className="px-5 py-3.5">ERP ID</th>
                  <th className="px-5 py-3.5">Department</th>
                  <th className="px-5 py-3.5">Semester</th>
                  <th className="px-5 py-3.5">Assigned Mentors</th>
                  <th className="px-5 py-3.5">Risk Level</th>
                  <th className="px-5 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-sand-200 dark:divide-charcoal-700 text-ink-900 dark:text-sand-100">
                {students.map((st) => (
                  <tr
                    key={st.id}
                    className="hover:bg-cream-50/50 dark:hover:bg-charcoal-750/50 transition-colors"
                  >
                    <td className="px-5 py-4 font-semibold">
                      <Link to={`/students/${st.id}`} className="hover:text-clay-500">
                        {st.name}
                      </Link>
                    </td>
                    <td className="px-5 py-4 font-mono text-ink-600 dark:text-sand-300">
                      {st.erp_id}
                    </td>
                    <td className="px-5 py-4">{st.department}</td>
                    <td className="px-5 py-4 font-medium">Sem {st.semester}</td>
                    <td className="px-5 py-4">
                      {st.assigned_teacher_ids && st.assigned_teacher_ids.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {st.assigned_teacher_ids.map((tid) => (
                            <span
                              key={tid}
                              className="inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-semibold bg-sand-100 dark:bg-charcoal-700 text-ink-800 dark:text-sand-200 border border-sand-200 dark:border-charcoal-600"
                            >
                              👨‍🏫 {facultyMap[tid]?.name || 'Teacher'}
                            </span>
                          ))}
                        </div>
                      ) : (
                        <span className="text-sand-400 dark:text-charcoal-500 text-[11px] italic">
                          Unassigned
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      <RiskBadge
                        level={st.current_risk?.level || 'Insufficient Data'}
                        isEscalated={st.current_risk?.level === 'High'}
                      />
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link
                        to={`/students/${st.id}`}
                        className="px-3 py-1.5 rounded-lg bg-cream-100 dark:bg-charcoal-700 text-clay-600 dark:text-clay-400 font-semibold hover:bg-clay-500 hover:text-white transition-all inline-block"
                      >
                        Profile
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div className="p-4 border-t border-sand-200 dark:border-charcoal-700 flex items-center justify-between text-xs text-ink-500 dark:text-sand-400">
          <span>
            Showing {students.length} students {hasMore ? '(more available)' : ''}
          </span>
          <div className="flex space-x-2">
            <button
              onClick={handlePrevPage}
              disabled={cursorHistory.length === 0 || loading}
              className="inline-flex items-center px-3 py-1.5 rounded-lg border border-sand-300 dark:border-charcoal-700 hover:bg-sand-100 dark:hover:bg-charcoal-750 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="w-4 h-4 mr-1" /> Previous
            </button>
            <button
              onClick={handleNextPage}
              disabled={!hasMore || loading}
              className="inline-flex items-center px-3 py-1.5 rounded-lg border border-sand-300 dark:border-charcoal-700 hover:bg-sand-100 dark:hover:bg-charcoal-750 disabled:opacity-40 transition-colors"
            >
              Next <ChevronRight className="w-4 h-4 ml-1" />
            </button>
          </div>
        </div>
      </div>

      <ImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onImportComplete={() => {
          fetchStudents(undefined);
          setImportModalOpen(false);
        }}
      />

      <CreateStudentModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onCreated={() => {
          fetchStudents(undefined);
          setCreateModalOpen(false);
        }}
      />
    </div>
  );
};
