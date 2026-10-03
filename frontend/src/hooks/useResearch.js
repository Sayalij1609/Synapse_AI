import { useState, useRef, useCallback } from 'react';
import { API_BASE, getToken } from '../api';

const AGENTS = ['planner', 'search', 'reader', 'writer', 'critic'];

/**
 * Custom hook that manages the entire SSE research flow.
 * Upgraded to capture the full autonomous research architecture:
 * - Research plan (objective, subtasks, search queries, strategy)
 * - Live agent execution status for all 6 agents
 * - Verification iteration tracking
 * - Evidence claims with lineage
 * - Source metadata
 * - Verification progression status
 */
export default function useResearch() {
  const [agentStatuses, setAgentStatuses] = useState(
    () => Object.fromEntries(AGENTS.map(k => [k, 'idle']))
  );
  const [results, setResults] = useState({});
  const [metrics, setMetrics] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState(null);

  /* ── New: Research plan state ── */
  const [researchPlan, setResearchPlan] = useState(null);

  /* ── New: Live agent execution records ── */
  const [liveAgents, setLiveAgents] = useState({});

  /* ── New: Verification iteration state ── */
  const [verificationState, setVerificationState] = useState({
    currentIteration: 0,
    maxIterations: 3,
    status: 'idle', // idle | researching | verifying | additional_research | verified | completed
    history: [],
  });

  /* ── New: Evidence & claims ── */
  const [evidenceClaims, setEvidenceClaims] = useState({
    grounded: [],
    unsupported: [],
    insufficient: [],
    citationTrace: {},
    totalClaims: 0,
  });

  /* ── New: Source metadata ── */
  const [sourceProfiles, setSourceProfiles] = useState([]);

  const esRef = useRef(null);
  const t0Ref = useRef(null);

  const reset = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setAgentStatuses(Object.fromEntries(AGENTS.map(k => [k, 'idle'])));
    setResults({});
    setMetrics(null);
    setIsRunning(false);
    setError(null);
    setResearchPlan(null);
    setLiveAgents({});
    setVerificationState({
      currentIteration: 0,
      maxIterations: 3,
      status: 'idle',
      history: [],
    });
    setEvidenceClaims({
      grounded: [],
      unsupported: [],
      insufficient: [],
      citationTrace: {},
      totalClaims: 0,
    });
    setSourceProfiles([]);
    t0Ref.current = null;
  }, []);

  const computeMetrics = useCallback((report, feedback) => {
    const words = report ? report.split(/\s+/).filter(Boolean).length : 0;
    const urls = report ? (report.match(/https?:\/\/[^\s)]+/g) || []) : [];
    const duration = t0Ref.current
      ? ((Date.now() - t0Ref.current) / 1000).toFixed(1) + 's'
      : '—';
    let score = '—';
    if (feedback) {
      const m = feedback.match(/Score:\s*(\d+\/\d+)/i);
      if (m) score = m[1];
    }
    return {
      sources: urls.length || '—',
      words: words.toLocaleString(),
      duration,
      score,
    };
  }, []);

  /* ── Helper: Update a single live agent record ── */
  const updateLiveAgent = useCallback((agentKey, updates) => {
    setLiveAgents(prev => ({
      ...prev,
      [agentKey]: {
        ...prev[agentKey],
        startTime: prev[agentKey]?.startTime || Date.now(),
        ...updates,
      },
    }));
  }, []);

  const start = useCallback((topic, projectId = null) => {
    reset();
    setIsRunning(true);
    t0Ref.current = Date.now();
    setVerificationState(prev => ({ ...prev, status: 'researching' }));

    let report = '';
    let feedback = '';

    const token = getToken();
    let url = `${API_BASE}/run?topic=${encodeURIComponent(topic)}`;
    if (token) {
      url += `&token=${encodeURIComponent(token)}`;
    }
    if (projectId) {
      url += `&project_id=${encodeURIComponent(projectId)}`;
    }

    const es = new EventSource(url);
    esRef.current = es;

    es.onmessage = (e) => {
      let d;
      try { d = JSON.parse(e.data); } catch { return; }

      if (d.error) {
        setError(d.error);
        es.close();
        setIsRunning(false);
        setVerificationState(prev => ({ ...prev, status: 'idle' }));
        return;
      }

      /* ── COMPLETE ── */
      if (d.step === 'complete') {
        es.close();
        if (d.state) {
          setResults(prev => ({
            ...prev,
            evidence: typeof d.state.evidence_summary === 'object'
              ? JSON.stringify(d.state.evidence_summary, null, 2)
              : String(d.state.evidence_summary || prev.evidence || ''),
            sourceQualityProfiles: d.state.source_quality_profiles || prev.sourceQualityProfiles || [],
            sourceQualitySummary: d.state.evidence_summary?.source_quality || prev.sourceQualitySummary || null,
            verificationReport: d.state.verification_report || prev.verificationReport || null,
            failedSources: d.state.failed_sources || d.failed_sources || prev.failedSources || [],
            degradedModes: d.state.degraded_modes || d.degraded_modes || prev.degradedModes || [],
            telemetry: d.telemetry || d.state?.telemetry || prev.telemetry || null,
            agentRuns: d.agent_runs || d.state?.agent_runs || prev.agentRuns || [],
            reportHistory: d.state.report_history || prev.reportHistory || [],
          }));

          // Capture final source profiles
          if (d.state.source_quality_profiles) {
            setSourceProfiles(d.state.source_quality_profiles);
          }
        }
        setMetrics(computeMetrics(report, feedback));
        setIsRunning(false);
        setVerificationState(prev => ({ ...prev, status: 'completed' }));
        return;
      }

      /* ── TELEMETRY ── */
      if (d.step === 'telemetry') {
        setResults(prev => ({
          ...prev,
          telemetry: d.telemetry || prev.telemetry || null,
          agentRuns: d.agent_runs || prev.agentRuns || [],
        }));
        return;
      }

      /* ── PLANNER: Capture research plan structure ── */
      if (d.step === 'planner' && d.status === 'done') {
        const plan = d.plan || {};
        setResearchPlan({
          objective: plan.research_objective || plan.objective || topic,
          subtasks: d.subtasks || plan.subtasks || [],
          searchQueries: plan.search_queries || (d.subtasks || []).flatMap(st => st.search_queries || []),
          strategy: plan.strategy || plan.approach || '',
          planMarkdown: d.result || '',
        });
        updateLiveAgent('Planner', { status: 'completed', endTime: Date.now() });
      }

      /* ── SUBTASK PROGRESS ── */
      if (d.step === 'subtask_progress') {
        updateLiveAgent('Search', {
          status: 'running',
          discoveredUrls: (d.discovered_count || 0),
          subtaskStatus: d.status,
        });
        updateLiveAgent('Reader', {
          status: 'running',
          extractedDocs: (d.extracted_count || 0),
        });

        // Update individual subtask status in the research plan view
        if (d.subtask_id || d.question) {
          setResearchPlan(prev => {
            if (!prev) return prev;
            return {
              ...prev,
              subtasks: (prev.subtasks || []).map((st, idx) =>
                (st.subtask_id === d.subtask_id || st.question === d.question || `subtask_${idx + 1}` === d.subtask_id)
                  ? {
                      ...st,
                      status: d.status || 'completed',
                      discovered_count: (d.discovered_count !== undefined ? d.discovered_count : st.discovered_count),
                      extracted_count: (d.extracted_count !== undefined ? d.extracted_count : st.extracted_count),
                    }
                  : st
              ),
            };
          });
        }
        return;
      }

      /* ── SUBTASKS running ── */
      if (d.step === 'subtasks' && d.status === 'running') {
        updateLiveAgent('Search', { status: 'running', total: d.total });
        updateLiveAgent('Reader', { status: 'running' });

        // Mark all subtasks as 'running' in the planner view
        setResearchPlan(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            subtasks: (prev.subtasks || []).map(st => ({ ...st, status: 'running' })),
          };
        });
        return;
      }

      /* ── EVIDENCE ── */
      if (d.step === 'evidence' && d.status === 'done') {
        updateLiveAgent('Retrieval', { status: 'completed', endTime: Date.now() });

        // Capture source quality profiles for the source metadata panel
        if (d.source_quality_profiles) {
          setSourceProfiles(d.source_quality_profiles);
        }

        setResults(prev => ({
          ...prev,
          evidence: typeof d.summary === 'object'
            ? JSON.stringify(d.summary, null, 2)
            : String(d.summary || prev.evidence || ''),
          sourceQualityProfiles: d.source_quality_profiles || prev.sourceQualityProfiles || [],
          sourceQualitySummary: d.summary?.source_quality || prev.sourceQualitySummary || null,
          failedSources: d.failed_sources || prev.failedSources || [],
          degradedModes: d.degraded_modes || prev.degradedModes || [],
        }));
      }
      if (d.step === 'evidence' && d.status === 'running') {
        updateLiveAgent('Retrieval', { status: 'running', iteration: d.iteration || 1 });
      }

      /* ── WRITER with claims ── */
      if (d.step === 'writer' && d.status === 'done') {
        updateLiveAgent('Writer', { status: 'completed', endTime: Date.now() });

        // Capture structured claims from writer output
        if (d.grounded_claims || d.unsupported_claims || d.insufficient_claims) {
          setEvidenceClaims({
            grounded: d.grounded_claims || [],
            unsupported: d.unsupported_claims || [],
            insufficient: d.insufficient_claims || [],
            citationTrace: d.citation_trace || {},
            totalClaims: (d.grounded_claims?.length || 0) + (d.unsupported_claims?.length || 0) + (d.insufficient_claims?.length || 0),
          });
        }
      }
      if (d.step === 'writer' && d.status === 'running') {
        updateLiveAgent('Writer', { status: 'running', iteration: d.iteration || 1 });
      }

      /* ── VERIFIER ── */
      if (d.step === 'verifier' && d.status === 'running') {
        const iter = d.iteration || 1;
        const maxIter = d.max_iterations || 3;
        setVerificationState(prev => ({
          ...prev,
          currentIteration: iter,
          maxIterations: maxIter,
          status: 'verifying',
        }));
        updateLiveAgent('Verification', { status: 'running', iteration: iter });
      }
      if (d.step === 'verifier' && d.status === 'done') {
        const vRes = d.verification_result || {};
        const decision = d.decision || vRes.status || '';
        updateLiveAgent('Verification', {
          status: 'completed',
          endTime: Date.now(),
          decision,
          iteration: d.iteration,
        });
        setVerificationState(prev => ({
          ...prev,
          status: decision === 'verified' ? 'verified' : 'verifying',
          history: [...prev.history, { iteration: d.iteration, decision, result: vRes }],
        }));
      }

      /* ── RE-RESEARCH ── */
      if (d.step === 're_research' && d.status === 'running') {
        setVerificationState(prev => ({
          ...prev,
          status: 'additional_research',
        }));
      }
      if (d.step === 're_research' && d.status === 'done') {
        setVerificationState(prev => ({
          ...prev,
          currentIteration: d.iteration || prev.currentIteration + 1,
          status: 'researching',
        }));
      }

      /* ── CRITIC (finalized) ── */
      if (d.step === 'critic' && d.status === 'done') {
        setVerificationState(prev => ({ ...prev, status: 'verified' }));
      }

      /* ── Update legacy agent status ── */
      setAgentStatuses(prev => ({ ...prev, [d.step]: d.status }));

      /* ── SEARCH / READER completion ── */
      if (d.step === 'search' && d.status === 'done') {
        updateLiveAgent('Search', { status: 'completed', endTime: Date.now() });
      }
      if (d.step === 'reader' && d.status === 'done') {
        updateLiveAgent('Reader', { status: 'completed', endTime: Date.now() });
      }

      /* ── Collect results (backwards compatible) ── */
      if (d.status === 'done' && d.result) {
        setResults(prev => ({ ...prev, [d.step]: d.result }));
        if (d.step === 'writer') report = d.result;
        if (d.step === 'critic') feedback = d.result;
      }
    };

    es.onerror = () => {
      es.close();
      setError('Connection lost. Please try again.');
      setIsRunning(false);
      setVerificationState(prev => ({ ...prev, status: 'idle' }));
    };
  }, [reset, computeMetrics, updateLiveAgent]);

  return {
    start,
    reset,
    agentStatuses,
    results,
    metrics,
    isRunning,
    error,
    /* New state */
    researchPlan,
    liveAgents,
    verificationState,
    evidenceClaims,
    sourceProfiles,
  };
}
