// src/pages/Home.js
import React from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { FaVideo, FaFileUpload, FaChartLine } from 'react-icons/fa';

const Home = () => {
  const navigate = useNavigate();

  // Configurare animatii
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { opacity: 1, transition: { staggerChildren: 0.2 } }
  };

  const itemVariants = {
    hidden: { y: 50, opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { type: 'spring', stiffness: 50 } }
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      style={{ maxWidth: '1200px', margin: '0 auto', padding: '20px' }}
    >
      {/* --- HERO SECTION (Titlul Principal) --- */}
      <motion.div variants={itemVariants} style={{ textAlign: 'center', marginBottom: '60px' }}>
        <h1 className="glow-text" style={{ fontSize: '3rem', fontFamily: 'Orbitron', color: '#fff', marginBottom: '10px' }}>
          BUN VENIT IN FITAPP
        </h1>
        <p style={{ color: '#aaa', fontSize: '1.2rem', maxWidth: '600px', margin: '0 auto' }}>
          Platforma ta de analiza biomecanica. Alege modul de lucru si primeste feedback pentru imbunatatirea formei.
        </p>
      </motion.div>

      {/* --- GRID CU CARDURI --- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '30px' }}>

        {/* CARD 1: UPLOAD */}
        <motion.div
          variants={itemVariants}
          whileHover={{ scale: 1.02, translateY: -5 }}
          className="cyber-card"
          onClick={() => navigate('/analysis')}
          style={{ padding: '40px', cursor: 'pointer', position: 'relative', overflow: 'hidden', minHeight: '300px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center' }}
        >
           <div style={{ position: 'absolute', top: '-20px', right: '-20px', width: '100px', height: '100px', background: 'var(--neon-purple)', filter: 'blur(60px)', opacity: 0.3 }}></div>

           <FaFileUpload size={60} color="var(--neon-purple)" style={{ marginBottom: '20px' }} />
           <h2 style={{ fontFamily: 'Orbitron', marginBottom: '10px' }}>INCARCA VIDEO</h2>
           <p style={{ color: '#888' }}>Video deja filmat? Incarca-l aici pentru o analiza detaliata.</p>
           <button className="cyber-btn" style={{ marginTop: '20px', borderColor: 'var(--neon-purple)', color: 'var(--neon-purple)' }}>Analizeaza acum</button>
        </motion.div>

        {/* CARD 2: LIVE (Corectat) */}
        <motion.div
          variants={itemVariants}
          whileHover={{ scale: 1.02, translateY: -5 }}
          className="cyber-card"
          onClick={() => navigate('/live')}
          style={{ padding: '40px', cursor: 'pointer', position: 'relative', overflow: 'hidden', minHeight: '300px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center' }}
        >
          <div style={{ position: 'absolute', top: '-20px', left: '-20px', width: '100px', height: '100px', background: 'var(--neon-cyan)', filter: 'blur(60px)', opacity: 0.3 }}></div>

          <FaVideo size={60} color="var(--neon-cyan)" style={{ marginBottom: '20px' }} />
          <h2 style={{ fontFamily: 'Orbitron', marginBottom: '10px' }}>ANALIZA LIVE</h2>
          <p style={{ color: '#888' }}>Foloseste camera web pentru feedback in timp real. Ideal pentru antrenamente acasa.</p>
          <button className="cyber-btn" style={{ marginTop: '20px' }}>Porneste Camera</button>
        </motion.div>

      </div>

      {/* --- INFO SECTION --- */}
      <motion.div
        initial={{ opacity: 0, y: 50 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.8 }}
        style={{ marginTop: '100px', padding: '40px', background: 'rgba(255,255,255,0.02)', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '30px' }}
      >
        <div style={{ flex: 1 }}>
          <h3 style={{ fontFamily: 'Orbitron', color: 'var(--neon-green)', marginBottom: '15px' }}> <FaChartLine style={{marginRight: '10px'}}/> FEEDBACK BIOMECANIC</h3>
          <p style={{ color: '#ccc', lineHeight: '1.6' }}>
            Aplicatia foloseste MediaPipe si calcule geometrice pentru a determina unghiurile articulatiilor tale. Indiferent daca faci genoflexiuni sau fandari, primesti feedback instantaneu despre siguranta si eficienta miscarii.
          </p>
        </div>
      </motion.div>

    </motion.div>
  );
};

export default Home;
