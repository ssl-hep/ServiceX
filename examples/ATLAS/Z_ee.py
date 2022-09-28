from func_adl_servicex import ServiceXSourceXAOD

query = "(call ResultTTree (call Select (call SelectMany (call EventDataset (list 'localds:bogus')) (lambda (list e) (call (attr e 'Jets') 'AntiKt4EMTopoJets'))) (lambda (list j) (/ (call (attr j 'pt')) 1000.0))) (list 'JetPt') 'analysis' 'junk.root')"
big_dataset = "rucio://mc15_13TeV:mc15_13TeV.361106.PowhegPythia8EvtGen_AZNLOCTEQ6L1_Zee.merge.DAOD_STDM3.e3601_s2576_s2132_r6630_r6264_p2363_tid05630052_00?files=3"
dataset = "mc16_13TeV:DAOD_TOPQ1.25521529._000009.pool.root.1"
ds = ServiceXSourceXAOD(dataset, backend="local")
leptons_per_event_query = ds \
        .Select(lambda e: e.Electrons("Electrons")) \
        .Select(lambda eles: eles.Where(lambda e: e.pt()/1000.0 > 30.0)) \
        .Select(lambda eles: eles.Where(lambda e: abs(e.eta()) < 2.5)) \
        .Where(lambda eles: len(eles) == 2) \
        .Select(lambda ls: (ls.Select(lambda e: e.pt()/1000.0), ls.Select(lambda e: e.eta()), ls.Select(lambda e: e.phi()), ls.Select(lambda e: e.m()/1000.0), ls.Select(lambda e: e.charge())))

print(leptons_per_event_query.AsPandasDF(('electrons_pt', 'electrons_eta', 'electrons_phi', 'electrons_mass', 'electrons_charge')).value())
