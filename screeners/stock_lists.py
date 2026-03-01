"""
Stock Lists — Predefined ticker groups for screening.
Based on TradingView sector classification (FactSet 20 sectors) for IDX stocks.
Last updated: February 2026
"""

STOCK_LISTS = {
    # ===== INDEKS UTAMA =====
    'idx_lq45': {
        'name': 'IDX LQ45',
        'description': '45 saham paling likuid di Bursa Efek Indonesia',
        'market': 'IDX',
        'tickers': [
            'ACES.JK', 'ADRO.JK', 'AMRT.JK', 'ANTM.JK', 'ASII.JK',
            'BBCA.JK', 'BBNI.JK', 'BBRI.JK', 'BBTN.JK', 'BMRI.JK',
            'BRIS.JK', 'BRPT.JK', 'BUKA.JK', 'CPIN.JK', 'EMTK.JK',
            'ESSA.JK', 'EXCL.JK', 'GGRM.JK', 'GOTO.JK', 'HRUM.JK',
            'ICBP.JK', 'INCO.JK', 'INDF.JK', 'INKP.JK', 'INTP.JK',
            'ITMG.JK', 'KLBF.JK', 'MAPI.JK', 'MDKA.JK', 'MEDC.JK',
            'MIKA.JK', 'PGAS.JK', 'PGEO.JK', 'PTBA.JK', 'SMGR.JK',
            'TBIG.JK', 'TINS.JK', 'TLKM.JK', 'TOWR.JK', 'TPIA.JK',
            'UNTR.JK', 'UNVR.JK', 'WMUU.JK',
        ]
    },

    # ===== 1. FINANSIAL — Finance =====
    'idx_finansial': {
        'name': 'Finansial',
        'description': 'Bank, pembiayaan, asuransi, sekuritas, properti & real estat, holding',
        'market': 'IDX',
        'tickers': [
            # Bank
            'BBCA.JK', 'BBRI.JK', 'BMRI.JK', 'BBNI.JK', 'BNLI.JK',
            'BRIS.JK', 'BNGA.JK', 'MEGA.JK', 'NISP.JK', 'BBHI.JK',
            'BINA.JK', 'BDMN.JK', 'PNBN.JK', 'ARTO.JK', 'BSIM.JK',
            'BTPN.JK', 'BBTN.JK', 'BBSI.JK', 'BBKP.JK', 'ADMF.JK',
            'BFIN.JK', 'BANK.JK', 'BTPS.JK', 'BMAS.JK', 'BJTM.JK',
            'BJBR.JK', 'BBMD.JK', 'MAYA.JK', 'AGRO.JK', 'YULE.JK',
            'BBYB.JK', 'MASB.JK', 'TRIM.JK', 'SDRA.JK', 'AMAR.JK',
            'NOBU.JK', 'BSWD.JK', 'INPC.JK', 'AGRS.JK', 'BGTG.JK',
            'BACA.JK', 'MCOR.JK', 'BNBA.JK', 'BCIC.JK', 'DNAR.JK',
            'BABP.JK', 'BVIC.JK', 'BKSW.JK', 'BEKS.JK', 'BSBK.JK',
            'PNBS.JK', 'SUPA.JK', 'BNII.JK',
            # Properti & Real Estat
            'MPRO.JK', 'CBDK.JK', 'BKSL.JK', 'BSDE.JK', 'PWON.JK',
            'KPIG.JK', 'CTRA.JK', 'JRPT.JK', 'DUTI.JK', 'LPKR.JK',
            'DMAS.JK', 'SMRA.JK', 'NIRO.JK', 'TUGU.JK', 'KIJA.JK',
            'MTLA.JK', 'RDTX.JK', 'LPCK.JK', 'SMDM.JK', 'ASRI.JK',
            'APLN.JK', 'ROCK.JK', 'GMTD.JK', 'ELTY.JK', 'FMII.JK',
            'MMLP.JK', 'MKPI.JK',
            # Pembiayaan, Asuransi, Holding
            'SMMA.JK', 'CASA.JK', 'RISE.JK', 'TBIG.JK', 'TOWR.JK',
            'LIFE.JK', 'APIC.JK', 'SRTG.JK', 'TRIN.JK', 'UANG.JK',
            'VICO.JK', 'STAR.JK', 'SKRN.JK', 'SFAN.JK', 'SMIL.JK',
            'BCAP.JK', 'IMJS.JK', 'AMAG.JK', 'LPGI.JK', 'PNLF.JK',
            'TRUE.JK',
        ]
    },

    # ===== 2. MINERAL ENERGI — Energy Minerals =====
    'idx_mineral_energi': {
        'name': 'Mineral Energi',
        'description': 'Batubara, minyak & gas, jasa pertambangan energi',
        'market': 'IDX',
        'tickers': [
            'DSSA.JK', 'BYAN.JK', 'UNTR.JK', 'BUMI.JK', 'ADMR.JK',
            'AADI.JK', 'ADRO.JK', 'GEMS.JK', 'MEDC.JK', 'ENRG.JK',
            'PTBA.JK', 'ITMG.JK', 'INDY.JK', 'HRUM.JK', 'DEWA.JK',
            'MCOL.JK', 'BIPI.JK', 'ESSA.JK', 'BSSR.JK', 'ABMM.JK',
            'TOBA.JK', 'ELSA.JK', 'SURE.JK', 'SMMT.JK', 'MYOH.JK',
            'MAHA.JK', 'DOID.JK', 'ITMA.JK', 'DWGL.JK', 'MBAP.JK',
            'SUNI.JK', 'KKGI.JK', 'ARII.JK', 'RMKO.JK', 'GTBO.JK',
            'CNKO.JK', 'COAL.JK', 'FIRE.JK', 'SICO.JK',
        ]
    },

    # ===== 3. MINERAL NON-ENERGI — Non-Energy Minerals =====
    'idx_mineral_non_energi': {
        'name': 'Mineral Non-Energi',
        'description': 'Pertambangan logam, semen, baja, mineral non-energi',
        'market': 'IDX',
        'tickers': [
            'AMMN.JK', 'CUAN.JK', 'BRPT.JK', 'BRMS.JK', 'EMAS.JK',
            'ANTM.JK', 'NCKL.JK', 'MBMA.JK', 'MDKA.JK', 'INCO.JK',
            'ARCI.JK', 'TINS.JK', 'INTP.JK', 'SMGR.JK', 'DSNG.JK',
            'PSAB.JK', 'CMNT.JK', 'NICL.JK', 'SGER.JK', 'KRAS.JK',
            'DKFT.JK', 'IFSH.JK', 'GGRP.JK', 'ISSP.JK', 'MARK.JK',
            'SMBR.JK', 'IFII.JK', 'NICE.JK', 'MINE.JK', 'HILL.JK',
            'BLES.JK', 'WSBP.JK', 'GDST.JK', 'ZINC.JK', 'SULI.JK',
        ]
    },

    # ===== 4. UTILITAS — Utilities =====
    'idx_utilitas': {
        'name': 'Utilitas',
        'description': 'Energi terbarukan, gas, listrik, air',
        'market': 'IDX',
        'tickers': [
            'BREN.JK', 'CDIA.JK', 'PGAS.JK', 'PGEO.JK', 'RAJA.JK',
            'POWR.JK', 'KEEN.JK', 'HGII.JK', 'LAPD.JK', 'CGAS.JK',
            'INPS.JK', 'MPOW.JK',
        ]
    },

    # ===== 5. INDUSTRI PROSES — Process Industries =====
    'idx_industri_proses': {
        'name': 'Industri Proses',
        'description': 'Kimia, kertas, perkebunan, pakan ternak, tekstil, kemasan',
        'market': 'IDX',
        'tickers': [
            'TPIA.JK', 'CPIN.JK', 'PGUN.JK', 'INKP.JK', 'JPFA.JK',
            'TAPG.JK', 'AVIA.JK', 'JARR.JK', 'TKIM.JK', 'NSSS.JK',
            'SMAR.JK', 'SSMS.JK', 'AALI.JK', 'SGRO.JK', 'STAA.JK',
            'TLDN.JK', 'PACK.JK', 'LSIP.JK', 'AGII.JK', 'PALM.JK',
            'ANJT.JK', 'UDNG.JK', 'BWPT.JK', 'TFCO.JK', 'FPNI.JK',
            'CPRO.JK', 'TBLA.JK', 'PBID.JK', 'SAMF.JK', 'ARGO.JK',
            'SIPD.JK', 'JAWA.JK', 'BISI.JK', 'DGWG.JK',
            # Page 2
            'MGRO.JK', 'PNGO.JK', 'MSJA.JK', 'BRAM.JK', 'CSRA.JK',
            'MLIA.JK', 'INDR.JK', 'MAIN.JK', 'NEST.JK', 'AYAM.JK',
            'TRGU.JK', 'AMFG.JK', 'ALDO.JK', 'SSTM.JK', 'GZCO.JK',
            'TRST.JK', 'BTEK.JK', 'NIKL.JK', 'BUDI.JK', 'PBRX.JK',
            'PDPP.JK', 'SPMA.JK', 'TALF.JK', 'ADMG.JK', 'WMUU.JK',
            'IPOL.JK', 'HOKI.JK', 'KDSI.JK', 'MOLI.JK', 'BRNA.JK',
            'EKAD.JK', 'SMKL.JK', 'MDKI.JK', 'CLPI.JK', 'IGAR.JK',
            'APLI.JK',
        ]
    },

    # ===== 6. LAYANAN TEKNOLOGI — Technology Services =====
    'idx_layanan_teknologi': {
        'name': 'Layanan Teknologi',
        'description': 'IT services, software, e-commerce, data center, fintech',
        'market': 'IDX',
        'tickers': [
            'DCII.JK', 'ASII.JK', 'MLPT.JK', 'GOTO.JK', 'WIFI.JK',
            'CYBR.JK', 'EDGE.JK', 'MSTI.JK', 'IRSX.JK', 'ASGR.JK',
            'ATIC.JK', 'AREA.JK', 'NFCX.JK', 'CHIP.JK', 'PGJO.JK',
            'AWAN.JK', 'VTNY.JK', 'TRON.JK', 'ELIT.JK', 'MCAS.JK',
            'LPLI.JK', 'JATI.JK', 'TFAS.JK', 'GPSO.JK', 'UVCR.JK',
            'TOSK.JK', 'WGSH.JK', 'CASH.JK', 'DIVA.JK', 'EPAC.JK',
            'RUNS.JK', 'INDX.JK', 'DIGI.JK', 'NINE.JK',
        ]
    },

    # ===== 7. KOMUNIKASI — Communications =====
    'idx_komunikasi': {
        'name': 'Komunikasi',
        'description': 'Telekomunikasi, ISP, menara, penyiaran',
        'market': 'IDX',
        'tickers': [
            'TLKM.JK', 'MORA.JK', 'DNET.JK', 'ISAT.JK', 'EXCL.JK',
            'MTEL.JK', 'INET.JK', 'LINK.JK', 'DATA.JK', 'CENT.JK',
            'GHON.JK', 'MSKY.JK', 'JAST.JK',
        ]
    },

    # ===== 8. KONSUMEN TIDAK TAHAN LAMA — Consumer Non-Durables =====
    'idx_konsumen_tidak_tahan_lama': {
        'name': 'Konsumen Tidak Tahan Lama',
        'description': 'Makanan, minuman, tembakau, produk rumah tangga, pakaian',
        'market': 'IDX',
        'tickers': [
            'PANI.JK', 'HMSP.JK', 'ICBP.JK', 'UNVR.JK', 'INDF.JK',
            'MYOR.JK', 'GGRM.JK', 'FAPA.JK', 'ULTJ.JK', 'POLU.JK',
            'YUPI.JK', 'GOOD.JK', 'STTP.JK', 'MLBI.JK', 'CLEO.JK',
            'ADES.JK', 'SIMP.JK', 'DMND.JK', 'ROTI.JK', 'FISH.JK',
            'UNIC.JK', 'WIIM.JK', 'VICI.JK', 'PSGO.JK', 'KEJU.JK',
            'CBUT.JK', 'BEEF.JK', 'EURO.JK', 'SKLT.JK', 'KINO.JK',
            'UCID.JK', 'STRK.JK', 'DLTA.JK', 'CEKA.JK', 'AISA.JK',
            # Page 2
            'CAMP.JK', 'TCID.JK', 'SKBM.JK', 'COCO.JK', 'BELL.JK',
            'BEER.JK', 'TRIS.JK', 'GUNA.JK', 'WINE.JK', 'SURI.JK',
            'MAXI.JK', 'CRAB.JK', 'ZONE.JK', 'SRSN.JK', 'ITIC.JK',
            'WAPO.JK', 'NAYZ.JK', 'ENZO.JK', 'BOBA.JK', 'DSFI.JK',
            'MBTO.JK', 'NASI.JK', 'ISEA.JK', 'IKAN.JK', 'TAYS.JK',
            'BATA.JK', 'SOUL.JK', 'RICY.JK', 'PCAR.JK', 'KLIN.JK',
            'BRRC.JK',
        ]
    },

    # ===== 9. LAYANAN KESEHATAN — Health Services =====
    'idx_layanan_kesehatan': {
        'name': 'Layanan Kesehatan',
        'description': 'Rumah sakit, klinik, laboratorium, layanan kesehatan',
        'market': 'IDX',
        'tickers': [
            'SRAJ.JK', 'SILO.JK', 'MIKA.JK', 'HEAL.JK', 'CARE.JK',
            'PRAY.JK', 'SAME.JK', 'PRDA.JK', 'MTMH.JK', 'BMHS.JK',
            'RSCH.JK', 'WIRG.JK', 'DGNS.JK', 'PRIM.JK', 'DKHH.JK',
        ]
    },

    # ===== 10. LAYANAN KONSUMEN — Consumer Services =====
    'idx_layanan_konsumen': {
        'name': 'Layanan Konsumen',
        'description': 'Hotel, restoran, media, hiburan, pariwisata, pendidikan',
        'market': 'IDX',
        'tickers': [
            'FILM.JK', 'EMTK.JK', 'BUVA.JK', 'MSIN.JK', 'SCMA.JK',
            'ALII.JK', 'CNMA.JK', 'INPP.JK', 'CLAY.JK', 'SINI.JK',
            'NATO.JK', 'JSPT.JK', 'FORE.JK', 'MAPB.JK', 'PNIN.JK',
            'BHIT.JK', 'MINA.JK', 'SOTS.JK', 'PSKT.JK', 'BLTZ.JK',
            'BMTR.JK', 'IPTV.JK', 'MDIA.JK', 'FAST.JK', 'OMRE.JK',
            'RAAM.JK', 'ARTA.JK', 'ENAK.JK', 'IBOS.JK', 'BOLA.JK',
            'SHID.JK', 'FITT.JK', 'PJAA.JK', 'PANR.JK', 'PZZA.JK',
            # Page 2
            'VIVA.JK', 'PNSE.JK', 'VERN.JK', 'ESTA.JK', 'BAYU.JK',
            'HAJJ.JK', 'PDES.JK', 'EAST.JK', 'HRME.JK', 'KBLV.JK',
            'AKKU.JK', 'DFAM.JK', 'PTSP.JK', 'ABBA.JK', 'MARI.JK',
            'SNLK.JK', 'TMPO.JK', 'RBMS.JK', 'PGLI.JK', 'CSMI.JK',
            'ICON.JK', 'PLAN.JK', 'RAFI.JK', 'BAIK.JK', 'KAQI.JK',
            'GRPH.JK', 'KDTN.JK',
        ]
    },

    # ===== 11. TRANSPORTASI — Transportation =====
    'idx_transportasi': {
        'name': 'Transportasi',
        'description': 'Pelayaran, penerbangan, logistik, jalan tol, transportasi darat',
        'market': 'IDX',
        'tickers': [
            'TCPI.JK', 'GIAA.JK', 'JSMR.JK', 'RMKE.JK', 'ELPI.JK',
            'SHIP.JK', 'CMNP.JK', 'GMFI.JK', 'TMAS.JK', 'BULL.JK',
            'SMDR.JK', 'SOCI.JK', 'CASS.JK', 'BESS.JK', 'GTSI.JK',
            'BIRD.JK', 'HUMI.JK', 'ASSA.JK', 'CBRE.JK', 'MBSS.JK',
            'HATM.JK', 'PORT.JK', 'WINS.JK', 'IPCC.JK', 'TPMA.JK',
            'PSSI.JK', 'BBRM.JK', 'IPCM.JK', 'PSAT.JK', 'TAMU.JK',
            'BLOG.JK', 'MITI.JK', 'BLTA.JK', 'CMPP.JK',
            # Page 2
            'NELY.JK', 'BOAT.JK', 'GTRA.JK', 'BSML.JK', 'HAIS.JK',
            'RIGS.JK', 'KLAS.JK', 'SAFE.JK', 'MPXL.JK', 'PURA.JK',
            'SAPX.JK', 'SDMU.JK', 'WEHA.JK', 'TAXI.JK', 'LAJU.JK',
            'HELI.JK', 'TRUK.JK', 'KARW.JK', 'PTIS.JK', 'CANI.JK',
            'PPGL.JK', 'JAYA.JK', 'LRNA.JK', 'TNCA.JK', 'KJEN.JK',
            'ARKA.JK', 'PJHB.JK', 'LOPI.JK',
        ]
    },

    # ===== 12. PERDAGANGAN RITEL — Retail Trade =====
    'idx_perdagangan_ritel': {
        'name': 'Perdagangan Ritel',
        'description': 'Supermarket, department store, e-commerce, toko retail',
        'market': 'IDX',
        'tickers': [
            'AMRT.JK', 'BELI.JK', 'MDIY.JK', 'MAPI.JK', 'MAPA.JK',
            'BUKA.JK', 'MIDI.JK', 'ACES.JK', 'BOGA.JK', 'LPPF.JK',
            'DAYA.JK', 'RALS.JK', 'ERAL.JK', 'MLPL.JK', 'HERO.JK',
            'PMJS.JK', 'DEPO.JK', 'SONA.JK', 'CARS.JK', 'RANC.JK',
            'BABY.JK', 'ZATA.JK', 'KONI.JK', 'MPPA.JK', 'UFOE.JK',
            'MDRN.JK', 'DOSS.JK', 'DEWI.JK', 'ECII.JK', 'KIOS.JK',
        ]
    },

    # ===== 13. PRODUSEN PABRIKAN — Producer Manufacturing =====
    'idx_produsen_pabrikan': {
        'name': 'Produsen Pabrikan',
        'description': 'Otomotif, kabel, keramik, baja, peralatan listrik',
        'market': 'IDX',
        'tickers': [
            'IMPC.JK', 'AUTO.JK', 'SMSM.JK', 'INDS.JK', 'DRMA.JK',
            'BUKK.JK', 'ARNA.JK', 'TOTO.JK', 'MKAP.JK', 'BOLT.JK',
            'KMTR.JK', 'SCCO.JK', 'KBLI.JK', 'TBMS.JK', 'VOKS.JK',
            'JECC.JK', 'HOPE.JK', 'HALO.JK', 'CCSI.JK', 'KBLM.JK',
            'ASPR.JK', 'PART.JK', 'LION.JK', 'IKAI.JK', 'AMIN.JK',
            'BINO.JK', 'OBAT.JK', 'APII.JK', 'CINT.JK', 'SEMA.JK',
            'KRYA.JK', 'GEMA.JK', 'ISAP.JK', 'KUAS.JK', 'INCF.JK',
        ]
    },

    # ===== 14. LAYANAN INDUSTRI — Industrial Services =====
    'idx_layanan_industri': {
        'name': 'Layanan Industri',
        'description': 'Konstruksi, jasa pertambangan, menara, pengelolaan kawasan industri',
        'market': 'IDX',
        'tickers': [
            'PTRO.JK', 'ARKO.JK', 'BNBR.JK', 'IBST.JK', 'SSIA.JK',
            'BALI.JK', 'CTBN.JK', 'PBSA.JK', 'RONY.JK', 'TOTL.JK',
            'ASLI.JK', 'PKPK.JK', 'ACST.JK', 'PTPP.JK', 'NRCA.JK',
            'PPRE.JK', 'KETR.JK', 'ADHI.JK', 'TEBE.JK', 'JKON.JK',
            'BBSS.JK', 'BEST.JK', 'LEAD.JK', 'MHKI.JK', 'PTPW.JK',
            'WTON.JK', 'APEX.JK', 'BDKR.JK', 'DGIK.JK', 'KOKA.JK',
            'WEGE.JK', 'IDPR.JK', 'UNIQ.JK', 'SOLA.JK', 'ATLA.JK',
        ]
    },

    # ===== 15. LAYANAN DISTRIBUSI — Distribution Services =====
    'idx_layanan_distribusi': {
        'name': 'Layanan Distribusi',
        'description': 'Distributor, grosir, perdagangan komoditas',
        'market': 'IDX',
        'tickers': [
            'CMRY.JK', 'AKRA.JK', 'TSPC.JK', 'DAAZ.JK', 'ERAA.JK',
            'EPMT.JK', 'TGKA.JK', 'MPMX.JK', 'HEXA.JK', 'MDLA.JK',
            'BLUE.JK', 'VISI.JK', 'IATA.JK', 'FOLK.JK', 'SPTO.JK',
            'CSAP.JK', 'LTLS.JK', 'LIVE.JK', 'BUAH.JK', 'ASLC.JK',
            'SMGA.JK', 'MMIX.JK', 'PEVE.JK', 'DPUM.JK', 'PMUI.JK',
            'UNSP.JK', 'TIRA.JK', 'IRRA.JK', 'BIKE.JK', 'LABS.JK',
            'GLVA.JK', 'KMDS.JK', 'IOTF.JK', 'SMLE.JK', 'BMSR.JK',
        ]
    },

    # ===== 16. TEKNOLOGI KESEHATAN — Health Technology =====
    'idx_teknologi_kesehatan': {
        'name': 'Teknologi Kesehatan',
        'description': 'Farmasi, alat kesehatan, bioteknologi',
        'market': 'IDX',
        'tickers': [
            'KLBF.JK', 'SOHO.JK', 'SIDO.JK', 'OMED.JK', 'PYFA.JK',
            'KAEF.JK', 'DVLA.JK', 'MERK.JK', 'CHEK.JK', 'IKPM.JK',
            'MEDS.JK', 'RLCO.JK',
        ]
    },

    # ===== 17. KONSUMEN TAHAN LAMA — Consumer Durables =====
    'idx_konsumen_tahan_lama': {
        'name': 'Konsumen Tahan Lama',
        'description': 'Otomotif, ban, furniture, properti, barang tahan lama',
        'market': 'IDX',
        'tickers': [
            'VKTR.JK', 'CITA.JK', 'HRTA.JK', 'MGLV.JK', 'IMAS.JK',
            'GJTL.JK', 'POLI.JK', 'WOOD.JK', 'KSIX.JK', 'RODA.JK',
            'UNTD.JK', 'DART.JK', 'GPRA.JK', 'SCNP.JK', 'GDYR.JK',
            'TYRE.JK', 'NTBK.JK', 'MANG.JK', 'CAKK.JK', 'INTD.JK',
            'LMPI.JK', 'LAND.JK', 'OLIV.JK', 'PTDU.JK', 'TAMA.JK',
            'KICI.JK', 'BAPA.JK', 'SPRE.JK',
        ]
    },

    # ===== 18. LAYANAN KOMERSIL — Commercial Services =====
    'idx_layanan_komersil': {
        'name': 'Layanan Komersil',
        'description': 'Jasa komersial, percetakan, keamanan, pendidikan, media',
        'market': 'IDX',
        'tickers': [
            'PNLF.JK', 'BHAT.JK', 'BPII.JK', 'MNCN.JK', 'JTPE.JK',
            'GOLF.JK', 'OASA.JK', 'FUTR.JK', 'LUCY.JK', 'DMMX.JK',
            'MKTR.JK', 'DOOH.JK', 'NETV.JK', 'FORU.JK', 'LFLO.JK',
            'PADA.JK', 'SOSS.JK', 'KING.JK', 'DYAN.JK', 'HYGN.JK',
            'NAIK.JK', 'CRSN.JK', 'MUTU.JK', 'MEJA.JK', 'NANO.JK',
            'MERI.JK', 'IDEA.JK', 'MPIX.JK', 'HDIT.JK', 'BMBL.JK',
            'TOOL.JK',
        ]
    },

    # ===== 19. LAIN-LAIN — Miscellaneous =====
    'idx_lain_lain': {
        'name': 'Lain-lain',
        'description': 'Perusahaan yang tidak masuk klasifikasi sektor utama',
        'market': 'IDX',
        'tickers': [
            'COIN.JK', 'RATU.JK',
        ]
    },

    # ===== 20. TEKNOLOGI ELEKTRONIK — Electronic Technology =====
    'idx_teknologi_elektronik': {
        'name': 'Teknologi Elektronik',
        'description': 'Elektronik, komputer, semikonduktor, kabel',
        'market': 'IDX',
        'tickers': [
            'MTDL.JK', 'PTSN.JK', 'AXIO.JK', 'IKBI.JK', 'ZYRX.JK',
            'LPIN.JK', 'RCCC.JK',
        ]
    },

    # ===== INTERNATIONAL =====
    'sp500_top50': {
        'name': 'S&P 500 Top 50 (USA)',
        'description': '50 saham terbesar di indeks S&P 500',
        'market': 'US',
        'tickers': [
            'AAPL', 'MSFT', 'AMZN', 'NVDA', 'GOOGL', 'META', 'TSLA',
            'BRK-B', 'UNH', 'JNJ', 'XOM', 'JPM', 'V', 'PG', 'MA',
            'HD', 'CVX', 'MRK', 'LLY', 'ABBV', 'PEP', 'KO', 'COST',
            'AVGO', 'WMT', 'MCD', 'CSCO', 'ACN', 'TMO', 'ABT',
            'CRM', 'DHR', 'NFLX', 'AMD', 'ORCL', 'INTC', 'DIS',
            'NKE', 'ADBE', 'TXN', 'PM', 'UNP', 'NEE', 'RTX',
            'LOW', 'QCOM', 'BA', 'SPGI', 'INTU', 'AMAT',
        ]
    },


}

# ===== AUTO-GENERATED: Semua IHSG (gabungan semua sektor IDX) =====
_all_idx_tickers = []
_seen = set()
for _key, _val in STOCK_LISTS.items():
    if _val.get('market') == 'IDX':
        for _t in _val['tickers']:
            if _t not in _seen:
                _all_idx_tickers.append(_t)
                _seen.add(_t)

STOCK_LISTS['idx_all_ihsg'] = {
    'name': 'IHSG',
    'description': 'Seluruh saham di Bursa Efek Indonesia (gabungan semua sektor)',
    'market': 'IDX',
    'tickers': sorted(_all_idx_tickers),
}
