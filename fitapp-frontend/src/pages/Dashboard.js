import React, { useState, useEffect } from 'react';
import { getHistory, deleteWorkout } from '../api';
import { motion, AnimatePresence } from 'framer-motion';
import { FaCalendarAlt, FaImages, FaTimes, FaChevronLeft, FaChevronRight, FaTrash } from 'react-icons/fa';

const Dashboard = () => {
  const [history, setHistory] = useState([]);
  const [selectedWorkout, setSelectedWorkout] = useState(null);
  const [currentRepIdx, setCurrentRepIdx] = useState(0);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = () => {
    getHistory().then(res => {
      setHistory(Array.isArray(res.data) ? res.data : []);
    }).catch(err => {
      console.error(err);
      setHistory([]);
    });
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    
    if (window.confirm("Esti sigur că vrei să stergi acest antrenament definitiv?")) {
        try {
            await deleteWorkout(id);
            // Actualizam lista local fara refresh la pagina
            setHistory(prev => prev.filter(item => item.id !== id));
        } catch (err) {
            alert("Eroare la stergere.");
        }
    }
  };

  const openWorkout = (workout) => {
    setSelectedWorkout(workout);
    setCurrentRepIdx(0);
  };

  const nextRep = () => {
    if (selectedWorkout && selectedWorkout.reps) {
        setCurrentRepIdx((prev) => (prev + 1) % selectedWorkout.reps.length);
    }
  };

  const prevRep = () => {
    if (selectedWorkout && selectedWorkout.reps) {
        setCurrentRepIdx((prev) => (prev - 1 + selectedWorkout.reps.length) % selectedWorkout.reps.length);
    }
  };

  const selectedItem = selectedWorkout?.reps?.[currentRepIdx] || {};
  const isPlankFrame = selectedItem.analysis_type === 'plank_frame' || selectedWorkout?.exercise === 'Plank';
  const itemLabel = isPlankFrame ? 'CADRU' : 'REP';

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
      <h2 className="glow-text" style={{ fontFamily: 'Orbitron', color: 'var(--neon-cyan)', marginBottom: '30px' }}>
        ISTORIC ANTRENAMENTE
      </h2>

      {history.length === 0 ? (
        <p style={{ color: '#666' }}>Nu ai antrenamente salvate.</p>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '20px' }}>
          {history.map((item) => (
            <motion.div 
              key={item.id}
              whileHover={{ scale: 1.03 }}
              onClick={() => openWorkout(item)}
              className="cyber-card" 
              style={{ padding: '20px', cursor: 'pointer', position: 'relative' }}
            >
              {/* BUTON STERGERE (Pozitionat Absolute Dreapta Sus) */}
              <button 
                onClick={(e) => handleDelete(e, item.id)}
                style={{
                    position: 'absolute',
                    top: '15px',
                    right: '15px',
                    background: 'transparent',
                    border: 'none',
                    color: '#ff4d4d',
                    cursor: 'pointer',
                    fontSize: '16px',
                    zIndex: 10
                }}
                title="Șterge Antrenament"
              >
                <FaTrash />
              </button>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingRight: '30px' }}>
                <h3 style={{ margin: 0, fontSize: '1.2rem' }}>{item.exercise}</h3>
              </div>
              
              <div style={{ margin: '10px 0' }}>
                 <span style={{ fontFamily: 'Orbitron', fontSize: '2rem', color: item.avg_score >= 80 ? 'var(--neon-green)' : 'orange' }}>
                  {parseInt(item.avg_score)}%
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', marginTop: '10px', color: '#666', fontSize: '0.9rem' }}>
                <FaCalendarAlt style={{ marginRight: '5px' }} /> {item.created_at}
              </div>
              <div style={{ marginTop: '15px', display: 'flex', alignItems: 'center', color: 'var(--neon-cyan)' }}>
                <FaImages style={{ marginRight: '5px' }} /> 
                Vezi {item.reps ? item.reps.length : 0} {item.exercise === 'Plank' ? 'Cadre' : 'Repetari'}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {/* MODAL GALERIE REPETARI (Ramane neschimbat) */}
      <AnimatePresence>
        {selectedWorkout && (
          <motion.div 
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ 
              position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', 
              background: 'rgba(0,0,0,0.95)', zIndex: 100, 
              display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '20px' 
            }}
            onClick={() => setSelectedWorkout(null)}
          >
            <div 
              className="cyber-card" 
              style={{ width: '100%', maxWidth: '900px', padding: '0', overflow: 'hidden', position: 'relative', background: '#0a0a0f' }} 
              onClick={e => e.stopPropagation()}
            >
              <div style={{ padding: '15px', borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0, fontFamily: 'Orbitron' }}>
                      {selectedWorkout.exercise} - <span style={{ color: 'var(--neon-green)' }}>{parseInt(selectedWorkout.avg_score)}%</span>
                  </h3>
                  <button onClick={() => setSelectedWorkout(null)} style={{ background: 'none', border: 'none', color: '#fff', fontSize: '20px', cursor: 'pointer' }}><FaTimes /></button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px', minHeight: '400px' }}>
                  {(!selectedWorkout.reps || selectedWorkout.reps.length === 0) ? (
                      <p>Nu exista cadre salvate pentru acest antrenament.</p>
                  ) : (
                      <>
                        <button onClick={prevRep} className="cyber-btn" style={{ padding: '15px' }}><FaChevronLeft /></button>
                        
                        <div style={{ flex: 1, margin: '0 20px', textAlign: 'center' }}>
                            <div style={{ position: 'relative', display: 'inline-block', width: '100%' }}>
                                <img 
                                    src={selectedWorkout.reps[currentRepIdx].image} 
                                    style={{ maxWidth: '100%', maxHeight: '50vh', borderRadius: '8px', border: '1px solid #333' }} 
                                    alt={isPlankFrame ? 'Cadru analizat' : 'Repetare'}
                                />
                                <div style={{ position: 'absolute', top: 10, left: 10, background: 'rgba(0,0,0,0.7)', padding: '5px 10px', borderRadius: '4px', color: 'var(--neon-cyan)' }}>
                                    {itemLabel} #{selectedWorkout.reps[currentRepIdx].id}
                                </div>
                                <div style={{ position: 'absolute', top: 10, right: 10, background: 'rgba(0,0,0,0.7)', padding: '5px 10px', borderRadius: '4px', fontWeight: 'bold', color: selectedWorkout.reps[currentRepIdx].score > 80 ? 'lime' : 'orange' }}>
                                    {selectedWorkout.reps[currentRepIdx].score}%
                                </div>
                            </div>

                            <div style={{ marginTop: '20px', textAlign: 'left', background: '#111', padding: '15px', borderRadius: '8px' }}>
                                <h4 style={{ margin: '0 0 10px 0', color: '#888' }}>FEEDBACK:</h4>
                                <ul style={{ margin: 0, paddingLeft: '20px', color: '#ddd' }}>
                                    {selectedWorkout.reps[currentRepIdx].feedback.map((fb, i) => (
                                        <li key={i}>{fb}</li>
                                    ))}
                                </ul>
                            </div>
                        </div>

                        <button onClick={nextRep} className="cyber-btn" style={{ padding: '15px' }}><FaChevronRight /></button>
                      </>
                  )}
              </div>
              
              <div style={{ padding: '10px', textAlign: 'center', fontSize: '12px', color: '#666' }}>
                  {isPlankFrame ? 'Cadrul' : 'Repetarea'} {currentRepIdx + 1} din {selectedWorkout.reps ? selectedWorkout.reps.length : 0}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default Dashboard;
