#ifndef analysis_query_H
#define analysis_query_H

#include <AnaAlgorithm/AnaAlgorithm.h>

class query : public EL::AnaAlgorithm
{
public:
  // this is a standard algorithm constructor
  query (const std::string& name, ISvcLocator* pSvcLocator);

  // these are the functions inherited from Algorithm
  virtual StatusCode initialize () override;
  virtual StatusCode execute () override;
  virtual StatusCode finalize () override;

private:
  // Class level variables

  
  double _JetPt2;

  

};

#endif