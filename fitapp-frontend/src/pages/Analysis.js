import React, { useRef, useState } from 'react';
import api, { saveResult } from '../api';
import { useNavigate } from 'react-router-dom';
import { FaChevronLeft, FaChevronRight } from 'react-icons/fa';

const Analysis = () => {
  const navigate = useNavigate();

  // Upload
  const [file, setFile] = useState(null);
  const inputRef = useRef(null);

  // Drag & drop
  const [isDragging, setIsDragging] = useState(false);

  // Rezultate analiza
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [reps, setReps] = useState([]);
  const [avgScore, setAvgScore] = useState(0);
  const [currentRepIndex, setCurrentRepIndex] = useState(0);

  // Exercitiu detectat/final (din backend)
  const [detectedExercise, setDetectedExercise] = useState(null);
  const [finalExercise, setFinalExercise] = useState(null);

  // Manual override (doar in rezumat)
  const [showManualAtSummary, setShowManualAtSummary] = useState(false);
  const [manualExercise, setManualExercise] = useState('Genuflexiune');
  const currentItem = reps[currentRepIndex] || {};
  const isPlankFrame = currentItem.analysis_type === 'plank_frame' || finalExercise === 'Plank';
  const itemLabel = isPlankFrame ? 'CADRU' : 'REP';
  const hasAnalysisResult = Boolean(finalExercise || detectedExercise || reps.length > 0);

  const startVideoAnalysis = (selectedFile, selectedExercise) => {
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('exercise', selectedExercise);

    return api.post('/analyze/start', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  };

  const getAnalysisStatus = (jobId) => api.get(`/analyze/status/${jobId}`);

  const pickFile = () => inputRef.current?.click();

  const acceptFile = (f) => {
    if (!f) return;

    if (!f.type?.startsWith('video/')) {
      alert('Te rog incarca un fisier video.');
      return;
    }

    setFile(f);

    // daca user schimba fisierul dupa o analiza, resetam rezultatele
    setReps([]);
    setAvgScore(0);
    setCurrentRepIndex(0);
    setDetectedExercise(null);
    setFinalExercise(null);
    setShowManualAtSummary(false);
    setProgress(0);
  };

  // Drag & drop handlers
  const onDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const onDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const onDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const dropped = e.dataTransfer?.files?.[0];
    if (dropped) acceptFile(dropped);
  };

  // Proceseaza video (Auto sau override manual)
  const handleProcess = async (overrideExercise = 'Auto') => {
    if (!file) {
      alert('Te rog incarca un video.');
      return;
    }

    setLoading(true);
    setProgress(0);

    try {
      const startRes = await startVideoAnalysis(file, overrideExercise);
      const jobId = startRes.data.job_id;

      if (!jobId) {
        throw new Error('Backend-ul nu a returnat job_id.');
      }

      let result = null;

      while (true) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        const statusRes = await getAnalysisStatus(jobId);
        const job = statusRes.data;

        setProgress(job.progress || 0);

        if (job.status === 'done') {
          result = job.result;
          break;
        }

        if (job.status === 'error') {
          throw new Error(job.error || 'Analiza a esuat.');
        }
      }

      setReps(result.reps || []);
      setAvgScore(result.avg_score || 0);
      setCurrentRepIndex(0);

      setDetectedExercise(result.detected_exercise || null);
      setFinalExercise(
        result.final_exercise || (overrideExercise !== 'Auto' ? overrideExercise : null)
      );

      setShowManualAtSummary(false);
      setProgress(100);
    } catch (err) {
      console.error(err);
      alert(err.message || 'Eroare la procesare. Verifica backend-ul si Network tab.');
    }

    setLoading(false);
  };

  const handleSave = async () => {
    try {
      const exerciseToSave = finalExercise || detectedExercise || 'Genuflexiune';

      const res = await saveResult({
        exercise: exerciseToSave,
        avg_score: avgScore,
        reps: reps,
      });

      const { xp_table, new_level, level_up, badges } = res.data;
      let msg = `SALVAT!\nTotal XP: +${xp_table?.total ?? 0}\n`;
      if (level_up) msg += `\nLEVEL UP: ${new_level}!`;
      if (badges && badges.length > 0) msg += `\nINSIGNE: ${badges.join(', ')}`;

      alert(msg);
      navigate('/history');
    } catch (err) {
      console.error(err);
      alert('Eroare la salvare (posibil sesiunea a expirat).');
    }
  };

  const nextRep = () => {
    if (!reps.length) return;
    setCurrentRepIndex((prev) => (prev + 1) % reps.length);
  };

  const prevRep = () => {
    if (!reps.length) return;
    setCurrentRepIndex((prev) => (prev - 1 + reps.length) % reps.length);
  };

  const resetAnalysis = () => {
    setReps([]);
    setAvgScore(0);
    setCurrentRepIndex(0);
    setDetectedExercise(null);
    setFinalExercise(null);
    setShowManualAtSummary(false);
    setManualExercise('Genuflexiune');
    setProgress(0);
    // pastram file ca sa poti reanaliza usor; daca vrei sa-l stergi: setFile(null)
  };

  const summaryExerciseLabel = () => {
    if (finalExercise) return finalExercise;
    if (detectedExercise) return detectedExercise;
    return '-';
  };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto' }}>
      <h2
        className="glow-text"
        style={{
          fontFamily: 'Orbitron',
          color: 'var(--neon-cyan)',
          marginBottom: '20px',
        }}
      >
        ANALIZA VIDEO
      </h2>

      {/* STARE 1: inainte de analiza */}
      {!hasAnalysisResult ? (
        <div className="cyber-card" style={{ padding: '32px' }}>
          {/* Zona Drag & Drop */}
          <div
            onClick={pickFile}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            style={{
              border: isDragging ? '2px dashed var(--neon-purple)' : '2px dashed rgba(0,255,255,0.35)',
              borderRadius: 14,
              padding: 28,
              cursor: 'pointer',
              textAlign: 'center',
              transition: '0.15s ease',
              background: isDragging ? 'rgba(160, 32, 240, 0.08)' : 'rgba(0,0,0,0.15)',
            }}
          >
            <div style={{ fontFamily: 'Orbitron', color: 'var(--neon-cyan)', fontSize: 16 }}>
              Trage si lasa videoclipul aici
            </div>
            <div style={{ marginTop: 10, color: '#bbb', fontSize: 13 }}>
              sau click pentru a selecta fisierul
            </div>

            <div style={{ marginTop: 14, color: '#fff', fontSize: 14 }}>
              {file ? (
                <>
                  <span style={{ color: 'var(--neon-purple)', fontFamily: 'Orbitron' }}>Selectat:</span>{' '}
                  {file.name}
                </>
              ) : (
                <span style={{ color: '#888' }}>Niciun fisier selectat</span>
              )}
            </div>
          </div>

          {/* Input ascuns */}
          <input
            ref={inputRef}
            type="file"
            accept="video/*"
            style={{ display: 'none' }}
            onChange={(e) => acceptFile(e.target.files?.[0] || null)}
          />

          <button
            onClick={() => handleProcess('Auto')}
            disabled={loading || !file}
            className="cyber-btn"
            style={{ width: '100%', marginTop: 18 }}
          >
            {loading ? 'PROCESARE...' : 'START'}
          </button>

          {loading && (
            <div style={{ marginTop: 18 }}>
              <div style={{ color: 'var(--neon-cyan)', fontFamily: 'Orbitron', fontSize: 13, marginBottom: 8 }}>
                Procesare video: {progress}%
              </div>
              <div style={{ height: 10, border: '1px solid rgba(0,255,255,0.35)', borderRadius: 999, overflow: 'hidden', background: 'rgba(255,255,255,0.08)' }}>
                <div
                  style={{
                    width: `${progress}%`,
                    height: '100%',
                    background: 'var(--neon-cyan)',
                    transition: 'width 0.25s ease',
                  }}
                />
              </div>
            </div>
          )}
        </div>
      ) : (
        /* STARE 2: dupa analiza (rezumat + reps) */
        <div>
          {/* Rezumat */}
          <div className="cyber-card" style={{ padding: '20px', textAlign: 'center', marginBottom: '20px' }}>
            <h3 style={{ color: 'var(--neon-purple)' }}>SCOR MEDIU: {avgScore}%</h3>

            <div style={{ marginTop: 8, color: 'var(--neon-cyan)', fontFamily: 'Orbitron', lineHeight: 1.6 }}>
              Exercitiu detectat: <span style={{ color: '#fff' }}>{detectedExercise || '-'}</span>
              <br />
              Exercitiu folosit: <span style={{ color: '#fff' }}>{summaryExerciseLabel()}</span>
            </div>

            <button
              type="button"
              onClick={() => setShowManualAtSummary((v) => !v)}
              className="cyber-btn"
              style={{ marginTop: 14 }}
              disabled={loading}
            >
              Schimba exercitiul
            </button>

            {showManualAtSummary && (
              <div style={{ marginTop: 12 }}>
                <select
                  className="cyber-input"
                  value={manualExercise}
                  onChange={(e) => setManualExercise(e.target.value)}
                  style={{ width: '100%', marginBottom: 10 }}
                >
                  <option value="Genuflexiune">Genuflexiune</option>
                  <option value="Flotare">Flotare</option>
                  <option value="Deadlift">Deadlift</option>
                  <option value="Fandare">Fandare</option>
                  <option value="Abdomene">Abdomene</option>
                  <option value="Tractiuni">Tractiuni</option>
                  <option value="Bench Press">Bench Press</option>
                  <option value="Biceps Curl">Biceps Curl</option>
                  <option value="Mountain Climbers">Mountain Climbers</option>
                  <option value="Lateral Raises">Lateral Raises</option>
                  <option value="Plank">Plank</option>
                </select>

                <button
                  type="button"
                  onClick={() => handleProcess(manualExercise)}
                  className="cyber-btn"
                  style={{ width: '100%' }}
                  disabled={loading || !file}
                >
                  {loading ? 'REANALIZEZ...' : 'Reanalizeaza cu selectia mea'}
                </button>

                {loading && (
                  <div style={{ marginTop: 12 }}>
                    <div style={{ color: 'var(--neon-cyan)', fontFamily: 'Orbitron', fontSize: 13, marginBottom: 8 }}>
                      Procesare video: {progress}%
                    </div>
                    <div style={{ height: 10, border: '1px solid rgba(0,255,255,0.35)', borderRadius: 999, overflow: 'hidden', background: 'rgba(255,255,255,0.08)' }}>
                      <div
                        style={{
                          width: `${progress}%`,
                          height: '100%',
                          background: 'var(--neon-cyan)',
                          transition: 'width 0.25s ease',
                        }}
                      />
                    </div>
                  </div>
                )}

                <div style={{ marginTop: 8, fontSize: 12, color: '#aaa' }}>
                  Reanalizeaza acelasi videoclip, dar forteaza exercitiul selectat.
                </div>
              </div>
            )}
          </div>

          {/* Viewer reps */}
          {reps.length === 0 ? (
            <div className="cyber-card" style={{ padding: 20, color: '#fff', textAlign: 'center' }}>
              <p style={{ margin: 0 }}>
                Analiza s-a finalizat, dar nu au fost detectate repetari complete. Incearca un video mai clar sau selecteaza manual exercitiul.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
              <button onClick={prevRep} className="cyber-btn" disabled={loading || reps.length === 0}>
                <FaChevronLeft />
              </button>

              <div className="cyber-card" style={{ flex: 1, padding: '10px', position: 'relative' }}>
                <div
                  style={{
                    position: 'absolute',
                    top: 10,
                    left: 10,
                    background: 'rgba(0,0,0,0.7)',
                    padding: '5px',
                    borderRadius: '5px',
                    color: 'var(--neon-cyan)',
                  }}
                >
                  {itemLabel} #{currentItem?.id ?? currentRepIndex + 1}
                </div>

                {reps[currentRepIndex]?.image ? (
                  <img
                    src={reps[currentRepIndex].image}
                    alt={isPlankFrame ? 'Cadru analizat' : 'Rep'}
                    style={{ width: '100%', borderRadius: '8px' }}
                  />
                ) : (
                  <div style={{ padding: 20, color: '#fff' }}>
                    {isPlankFrame ? 'Nu exista imagine pentru acest cadru.' : 'Nu exista imagine pentru aceasta repetare.'}
                  </div>
                )}

                <div style={{ marginTop: '10px' }}>
                  <h4 style={{ color: '#aaa' }}>FEEDBACK:</h4>
                  <ul>
                    {(reps[currentRepIndex]?.feedback || []).map((fb, i) => (
                      <li key={i} style={{ color: '#fff' }}>
                        {fb}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <button onClick={nextRep} className="cyber-btn" disabled={loading || reps.length === 0}>
                <FaChevronRight />
              </button>
            </div>
          )}

          {/* Actiuni */}
          <div style={{ marginTop: '30px', display: 'flex', gap: '10px' }}>
            <button
              onClick={handleSave}
              className="cyber-btn"
              style={{ flex: 1, borderColor: 'lime', color: 'lime' }}
              disabled={loading || reps.length === 0}
            >
              SALVEAZA
            </button>

            <button
              onClick={resetAnalysis}
              className="cyber-btn"
              style={{ flex: 1, borderColor: 'red', color: 'red' }}
              disabled={loading}
            >
              STERGE
            </button>

            <button
              onClick={() => handleProcess('Auto')}
              className="cyber-btn"
              style={{ flex: 1 }}
              disabled={loading || !file}
              title="Ruleaza din nou detectarea automata pe acelasi video"
            >
              REANALIZEAZA AUTO
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Analysis;
