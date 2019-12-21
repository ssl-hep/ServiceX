#
# Read the submission directory as a command line argument. You can
# extend the list of arguments with your private ones later on.
# Set up (Py)ROOT.
import ROOT
import optparse
from AnaAlgorithm.DualUseConfig import createAlgorithm

parser = optparse.OptionParser()

ROOT.xAOD.Init().ignore()
parser.add_option('-s', '--submission-dir', dest='submission_dir',
                  action='store', type='string', default='submitDir',
                  help='Submission directory for EventLoop')
(options, args) = parser.parse_args()


# Set up the sample handler object. See comments from the C++ macro
# for the details about these lines.
sh = ROOT.SH.SampleHandler()
sh.setMetaString('nc_tree', 'CollectionTree')
# ROOT.SH.ScanDir().filePattern( '' ).scan( sh, inputFilePath )
ROOT.SH.readFileList(sh, "ANALYSIS", "filelist.txt")
sh.printContent()

# Create an EventLoop job.
job = ROOT.EL.Job()
job.sampleHandler(sh)
# job.options().setDouble( ROOT.EL.Job.optMaxEvents, 500 )

# Commented out for now because it really slows things down. Uncomment and change
# the bank to be Analysis_NOSYS in query.cxx and it will work again.
# #Get the systematics tool in - because we need it.
# from AnaAlgorithm.AnaAlgorithmConfig import AnaAlgorithmConfig
# config = AnaAlgorithmConfig( 'CP::SysListLoaderAlg/SysLoaderAlg' )
# config.sigmaRecommended = 1
# job.algsAdd( config )

# # First step - run calibration for the jets so they are available to use when we want them.
# ROOT.CP.JetCalibrationAlg ("dummy", None)
# from JetAnalysisAlgorithms.JetAnalysisSequence import makeJetAnalysisSequence
# #from jetsequence import makeJetAnalysisSequence
# jetSequence = makeJetAnalysisSequence( 'data', "AntiKt4EMTopoJets" )
# jetSequence.configure( inputName = "AntiKt4EMTopoJets", outputName = 'AnalysisJets' )
# for alg in jetSequence:
#     job.algsAdd(alg)

# Create the algorithm's configuration.
alg = createAlgorithm('query', 'AnalysisAlg')
# later on we'll add some configuration options for our algorithm that go here

# Add our algorithm to the job
job.algsAdd(alg)
job.outputAdd(ROOT.EL.OutputStream('ANALYSIS'))

# Run the job using the direct driver.
driver = ROOT.EL.DirectDriver()
driver.submit(job, options.submission_dir)