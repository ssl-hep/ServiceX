FROM opensciencegrid/software-base:3.6-el8-release

RUN yum install -y epel-release.noarch && \
    yum clean all && \
    rm -rf /var/cache/yum
RUN yum upgrade -y && \
    yum clean all && \
    rm -rf /var/cache/yum

RUN yum install -y python39 python39-pip python39-psutil python39-requests 

RUN yum install -y https://repo.opensciencegrid.org/osg/3.6/osg-3.6-el8-release-latest.rpm
RUN yum install osg-ca-certs voms voms-clients fetch-crl -y

RUN yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-8.noarch.rpm; \
    curl -s -o /etc/pki/rpm-gpg/RPM-GPG-KEY-wlcg http://linuxsoft.cern.ch/wlcg/RPM-GPG-KEY-wlcg; \
    curl -s -o /etc/yum.repos.d/wlcg-centos8.repo http://linuxsoft.cern.ch/wlcg/wlcg-centos8.repo;

RUN yum install -y wlcg-voms-atlas wlcg-voms-cms

RUN rm /etc/alternatives/python3
RUN ln -s /usr/bin/python3.9 /etc/alternatives/python3

# Upgrade pip & setuptools and install Rucio
RUN python3 -m pip install --no-cache-dir --upgrade setuptools && \
    python3 -m pip install --no-cache-dir --pre rucio-clients && \
    python3 -m pip install --no-cache-dir jinja2 j2cli pyyaml argcomplete

# enable bash completion for the rucio clients
ADD init_rucio.sh /etc/profile.d/rucio_init.sh
ADD rucio.cfg /opt/rucio/etc/rucio.cfg
ENV PATH $PATH:/opt/rucio/bin

CMD ["/bin/bash"]