import source_navigation_steps
import functional_test


class TestSourceInterfaceBannerWarnings(
        functional_test.FunctionalTest,
        source_navigation_steps.SourceNavigationSteps):

    def test_not_found(self):
        self._source_not_found()
