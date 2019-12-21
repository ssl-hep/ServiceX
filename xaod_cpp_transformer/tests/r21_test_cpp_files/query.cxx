#include <AsgTools/MessageCheck.h>
#include <analysis/query.h>


#include "xAODJet/JetContainer.h"


#include <TTree.h>

query :: query (const std::string& name,
                                  ISvcLocator *pSvcLocator)
    : EL::AnaAlgorithm (name, pSvcLocator)
{
  // Here you put any code for the base initialization of variables,
  // e.g. initialize all pointers to 0.  This is also where you
  // declare all properties for your algorithm.  Note that things like
  // resetting statistics variables or booking histograms should
  // rather go into the initialize() function.
}

StatusCode query :: initialize ()
{
  // Here you do everything that needs to be done at the very
  // beginning on each worker node, e.g. create histograms and output
  // trees.  This method gets called before any input files are
  // connected.

  
  {
  
    ANA_CHECK (book (TTree ("analysis3", "My analysis ntuple")));
  
    auto myTree = tree ("analysis3");
  
    myTree->Branch("JetPt", &_JetPt2);
  
  }
  

  return StatusCode::SUCCESS;
}

StatusCode query :: execute ()
{
  // Here you do everything that needs to be done on every single
  // events, e.g. read input variables, apply cuts, and fill
  // histograms and trees.  This is where most of your actual analysis
  // code will go.

  
  {
  
    const xAOD::JetContainer* jets0;
  
    {
  
      const xAOD::JetContainer* result = 0;
  
      ANA_CHECK (evtStore()->retrieve(result, "AntiKt4EMTopoJets"));
  
      jets0 = result;
  
    }
  
    for (auto i_obj1 : *jets0)
  
    {
  
      _JetPt2 = (i_obj1->pt()/1000.0);
  
      tree("analysis3")->Fill();
  
    }
  
  }
  

  return StatusCode::SUCCESS;
}



StatusCode query :: finalize ()
{
  // This method is the mirror image of initialize(), meaning it gets
  // called after the last event has been processed on the worker node
  // and allows you to finish up any objects you created in
  // initialize() before they are written to disk.  This is actually
  // fairly rare, since this happens separately for each worker node.
  // Most of the time you want to do your post-processing on the
  // submission node after all your histogram outputs have been
  // merged.
  return StatusCode::SUCCESS;
}