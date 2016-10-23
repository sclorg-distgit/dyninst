%{?scl:%scl_package dyninst}

Summary: An API for Run-time Code Generation
License: LGPLv2+
Name: %{?scl_prefix}dyninst
Group: Development/Libraries
Release: 4%{?dist}
URL: http://www.dyninst.org
Version: 9.2.0
Exclusiveos: linux
#dyninst only knows the following architectures
ExclusiveArch: %{ix86} x86_64 ppc ppc64

Source0: https://github.com/dyninst/dyninst/archive/v9.2.0.tar.gz#/dyninst-%{version}.tar.gz
Source1: https://github.com/dyninst/dyninst/releases/download/v9.2.0/Testsuite-9.2.0.zip
Patch1: dyninst-9.2.0-stackanalysis-template-angle.patch
Patch2: dyninst-9.2.0-proccontrol-attach-no-exe.patch
Patch3: dyninst-9.2.0-ppc64-rel-type.patch
Patch4: dyninst-9.2.0-modify-data-64.patch
Patch5: dyninst-9.2.0-pr176-constrain-trymmap.patch

%global dyninst_base dyninst-%{version}
%global testsuite_base testsuite-master

Source3: https://www.prevanders.net/libdwarf-20160613.tar.gz
BuildRequires: zlib-devel
# XXX: temporarily bundled
# BuildRequires: %{scl_prefix}libdwarf-devel >= 20111030
BuildRoot: %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires: elfutils-libelf-devel
BuildRequires: boost-devel
BuildRequires: binutils-devel
BuildRequires: cmake
%{?scl:Requires: %scl_runtime}

# Extra requires just for the testsuite
# NB, there's no separate libstdc++-static for <=el6
%if 0%{?rhel} >= 7
BuildRequires: libstdc++-static
%endif
BuildRequires: gcc-gfortran glibc-static nasm

# Testsuite files should not provide/require anything
%{?filter_setup:
%filter_provides_in %{_libdir}/dyninst/testsuite/
%filter_requires_in %{_libdir}/dyninst/testsuite/
%filter_setup
}

%description

Dyninst is an Application Program Interface (API) to permit the insertion of
code into a running program. The API also permits changing or removing
subroutine calls from the application program. Run-time code changes are
useful to support a variety of applications including debugging, performance
monitoring, and to support composing applications out of existing packages.
The goal of this API is to provide a machine independent interface to permit
the creation of tools and applications that use run-time code patching.

%package doc
Summary: Documentation for using the Dyninst API
Group: Documentation
%description doc
dyninst-doc contains API documentation for the Dyninst libraries.

%package devel
Summary: Header files for the compiling programs with Dyninst
Group: Development/System
Requires: %{?scl_prefix}dyninst = %{version}-%{release}
Requires: boost-devel

%description devel
dyninst-devel includes the C header files that specify the Dyninst user-space
libraries and interfaces. This is required for rebuilding any program
that uses Dyninst.

%package static
Summary: Static libraries for the compiling programs with Dyninst
Group: Development/System
Requires: %{?scl_prefix}dyninst-devel = %{version}-%{release}
%description static
dyninst-static includes the static versions of the library files for
the dyninst user-space libraries and interfaces.

%package testsuite
Summary: Programs for testing Dyninst
Group: Development/System
Requires: %{?scl_prefix}dyninst = %{version}-%{release}
Requires: %{?scl_prefix}dyninst-devel = %{version}-%{release}
Requires: %{?scl_prefix}dyninst-static = %{version}-%{release}
Requires: glibc-static
%description testsuite
dyninst-testsuite includes the test harness and target programs for
making sure that dyninst works properly.

%prep
%setup -q -n %{name}-%{version} -c
%setup -q -T -D -a 1

%patch1 -p0 -b .template-export
%patch2 -p1 -d %{dyninst_base} -b .attach-no-exe
%patch3 -p1 -d %{dyninst_base} -b .ppc64-rel-type
%patch4 -p1 -d %{dyninst_base} -b .modify-data-64
%patch5 -p1 -d %{dyninst_base} -b .constrain-trymmap

# XXX: bundled libdwarf
%setup -q -T -D -b 3

%build

# bundled libdwarf build - assemble an .a archive, but built with -fPIC
pushd ../dwarf-20160613/libdwarf
libdwarf_builddir=`pwd`
%configure --disable-shared
make %{?_smp_mflags} dwfpic=-fPIC
popd

cd %{dyninst_base}

%cmake \
 -DENABLE_STATIC_LIBS=1 \
 -DCMAKE_BUILD_TYPE:STRING=None \
 -DINSTALL_LIB_DIR:PATH=%{_libdir}/dyninst \
 -DINSTALL_INCLUDE_DIR:PATH=%{_includedir}/dyninst \
 -DINSTALL_CMAKE_DIR:PATH=%{_libdir}/cmake/Dyninst \
 -DLIBDWARF_LIBRARIES:FILEPATH="$libdwarf_builddir/libdwarf.a;-lz" \
 -DLIBDWARF_INCLUDE_DIR:PATH=$libdwarf_builddir \
 -DBoost_NO_BOOST_CMAKE=ON \
 -DCMAKE_SKIP_RPATH:BOOL=YES
make %{?_smp_mflags}

# Hack to install dyninst nearby, so the testsuite can use it
make DESTDIR=../install install
find ../install -name '*.cmake' -execdir \
  sed -i -e 's!%{_prefix}!../install&!' '{}' '+'

cd ../%{testsuite_base}
%cmake \
 -DDyninst_DIR:PATH=$PWD/../install%{_libdir}/cmake/Dyninst \
 -DINSTALL_DIR:PATH=%{_libdir}/dyninst/testsuite \
 -DCMAKE_BUILD_TYPE:STRING=Debug \
 -DBoost_NO_BOOST_CMAKE=ON \
 -DCMAKE_SKIP_RPATH:BOOL=YES
make %{?_smp_mflags}

%install

cd %{dyninst_base}
make DESTDIR=$RPM_BUILD_ROOT install

# It doesn't install docs the way we want, so remove them.
# We'll just grab the pdfs later, directly from the build dir.
rm -v %{buildroot}%{_docdir}/*-%{version}.pdf

cd ../%{testsuite_base}
make DESTDIR=$RPM_BUILD_ROOT install

mkdir -p $RPM_BUILD_ROOT/etc/ld.so.conf.d
echo "%{_libdir}/dyninst" > $RPM_BUILD_ROOT/etc/ld.so.conf.d/%{name}-%{_arch}.conf

# Ugly hack to mask testsuite files from debuginfo extraction.  Running the
# testsuite requires debuginfo, so extraction is useless.  However, debuginfo
# extraction is still nice for the main libraries, so we don't want to disable
# it package-wide.  The permissions are restored by attr(755,-,-) in files.
find %{buildroot}%{_libdir}/dyninst/testsuite/ \
  -type f '!' -name '*.a' -execdir chmod 644 '{}' '+'

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%files
%defattr(-,root,root,-)

%dir %{_libdir}/dyninst
%{_libdir}/dyninst/*.so.*

%doc %{dyninst_base}/COPYRIGHT
%doc %{dyninst_base}/LGPL

%config(noreplace) /etc/ld.so.conf.d/*

%files doc
%defattr(-,root,root,-)
%doc %{dyninst_base}/dataflowAPI/doc/dataflowAPI.pdf
%doc %{dyninst_base}/dynC_API/doc/dynC_API.pdf
%doc %{dyninst_base}/dyninstAPI/doc/dyninstAPI.pdf
%doc %{dyninst_base}/instructionAPI/doc/instructionAPI.pdf
%doc %{dyninst_base}/parseAPI/doc/parseAPI.pdf
%doc %{dyninst_base}/patchAPI/doc/patchAPI.pdf
%doc %{dyninst_base}/proccontrol/doc/proccontrol.pdf
%doc %{dyninst_base}/stackwalk/doc/stackwalk.pdf
%doc %{dyninst_base}/symtabAPI/doc/symtabAPI.pdf

%files devel
%defattr(-,root,root,-)
%{_includedir}/dyninst
%{_libdir}/dyninst/*.so
%dir %{_libdir}/cmake
%{_libdir}/cmake/Dyninst

%files static
%defattr(-,root,root,-)
%{_libdir}/dyninst/*.a

%files testsuite
%defattr(-,root,root,-)
%{_bindir}/parseThat
%dir %{_libdir}/dyninst/testsuite/
# Restore the permissions that were hacked out above, during install.
%attr(755,root,root) %{_libdir}/dyninst/testsuite/*[!a]
%attr(644,root,root) %{_libdir}/dyninst/testsuite/*.a

%changelog
* Thu Sep 15 2016 Josh Stone <jistone@redhat.com> - 9.2.0-4
- rhbz1366656: fix ppc64 relocation rewriting
- rhbz1366726: check mmap constrains for locality
- rhbz1367225: fix x86 codegen for 64-bit offsets

* Tue Aug 09 2016 Josh Stone <jistone@redhat.com> - 9.2.0-3
- rhbz1363794: fix proccontrol attach without an exe.

* Tue Jul 26 2016 Josh Stone <jistone@redhat.com> - 9.2.0-2
- Patch a template '>>' in stackanalysis.h for pre-C++11 users.

* Thu Jul 21 2016 Josh Stone <jistone@redhat.com> - 9.2.0-1
- Update to 9.2.0

* Fri Mar 11 2016 Frank Ch. Eigler <fche@redhat.com> - 9.1.0-3
- Export libdyninstAPI_RT_init_maxthreads (ref rhbz1315841/1316956)

* Thu Feb 25 2016 Frank Ch. Eigler <fche@redhat.com> - 9.1.0-2
- buildroot bump respin

* Wed Jan 13 2016 Josh Stone <jistone@redhat.com> - 9.1.0-1
- Update to 9.1.0

* Mon Sep 21 2015 Josh Stone <jistone@redhat.com> - 8.2.1-5
- Rebuild for x86_64 only.

* Mon Sep 21 2015 Josh Stone <jistone@redhat.com> - 8.2.1-4
- rhbz1261061: Make sure the system's Boost.cmake is not used.

* Wed Jan 07 2015 Josh Stone <jistone@redhat.com> - 8.2.1-3
- Rebuild for x86_64 only.

* Wed Jan 07 2015 Josh Stone <jistone@redhat.com> - 8.2.1-2
- Rebuild for releng updates.

* Wed Dec 17 2014 Josh Stone <jistone@redhat.com> - 8.2.1-1
- Update to point release 8.2.1.

* Tue Aug 19 2014 Josh Stone <jistone@redhat.com> - 8.2.0-1
- final rebase to 8.2.0, using upstream tag "v8.2.0.1"

* Thu Jul 24 2014 Josh Stone <jistone@redhat.com> - 8.2.0-0.440.gde280f74f40e
- update to a newer pre-8.2.0 snapshot

* Wed May 21 2014 Josh Stone <jistone@redhat.com> - 8.2.0-0.374.g593fb2773a48
- more libdyninstAPI_RT symbols, and add testsuite requires

* Wed May 21 2014 Josh Stone <jistone@redhat.com> - 8.2.0-0.373.geaba204a72a3
- fix libdyninstAPI_RT.so symbol visibility

* Tue May 20 2014 Josh Stone <jistone@redhat.com> - 8.2.0-0.372.gdfd4a8842f4c
- prerelease build of dyninst 8.2.0

* Tue Nov 26 2013 Josh Stone <jistone@redhat.com> 8.0-6dw
- rhbz987096: backported upstream patches for mid-syscall PTRACE_EVENTs

* Wed Apr 17 2013 Josh Stone <jistone@redhat.com> 8.0-5dw
- rhbz855981: backported upstream patch to remove missing-dwarf asserts

* Tue Feb 26 2013 Frank Ch. Eigler <fche@redhat.com> 8.0-4dw
- fix %attr() of testsuite files

* Tue Feb 26 2013 Josh Stone <jistone@redhat.com> 8.0-3dw
- rhbz915820: Add a dyninst-testsuite package.

* Thu Jan 31 2013 Frank Ch. Eigler <fche@redhat.com> - 8.0-2dw
- convert to scl
- bundle libdwarf temporarily

* Tue Nov 20 2012 Josh Stone <jistone@redhat.com>
- Tweak the configure/make commands
- Disable the testsuite via configure.
- Set the private includedir and libdir via configure.
- Set VERBOSE_COMPILATION for make.
- Use DESTDIR for make install.

* Mon Nov 19 2012 Josh Stone <jistone@redhat.com> 8.0-1
- Update to release 8.0.
- Updated "%files doc" to reflect renames.
- Drop the unused BuildRequires libxml2-devel.
- Drop the 7.99.x version-munging patch.

* Fri Nov 09 2012 Josh Stone <jistone@redhat.com> 7.99.2-0.29
- Rebase to git e99d7070bbc39c76d6d528db530046c22681c17e

* Mon Oct 29 2012 Josh Stone <jistone@redhat.com> 7.99.2-0.28
- Bump to 7.99.2 per abi-compliance-checker results

* Fri Oct 26 2012 Josh Stone <jistone@redhat.com> 7.99.1-0.27
- Rebase to git dd8f40b7b4742ad97098613876efeef46d3d9e65
- Use _smp_mflags to enable building in parallel.

* Wed Oct 03 2012 Josh Stone <jistone@redhat.com> 7.99.1-0.26
- Rebase to git 557599ad7417610f179720ad88366c32a0557127

* Thu Sep 20 2012 Josh Stone <jistone@redhat.com> 7.99.1-0.25
- Rebase on newer git tree.
- Bump the fake version to 7.99.1 to account for ABI differences.
- Enforce the minimum libdwarf version.
- Drop the upstreamed R_PPC_NUM patch.

* Wed Aug 15 2012 Karsten Hopp <karsten@redhat.com> 7.99-0.24
- check if R_PPC_NUM is defined before using it, similar to R_PPC64_NUM

* Mon Jul 30 2012 Josh Stone <jistone@redhat.com> 7.99-0.23
- Rebase on newer git tree.
- Update license files with upstream additions.
- Split documentation into -doc subpackage.
- Claim ownership of %{_libdir}/dyninst.

* Fri Jul 27 2012 William Cohen <wcohen@redhat.com> - 7.99-0.22
- Correct requires for dyninst-devel.

* Wed Jul 25 2012 Josh Stone <jistone@redhat.com> - 7.99-0.21
- Rebase on newer git tree
- Update context in dyninst-git.patch
- Drop dyninst-delete_array.patch
- Drop dyninst-common-makefile.patch

* Wed Jul 18 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 7.99-0.20
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Mon Jul 16 2012 William Cohen <wcohen@redhat.com> - 7.99-0.19
- Patch common/i386-unknown-linux2.4/Makefile to build.

* Fri Jul 13 2012 William Cohen <wcohen@redhat.com> - 7.99-0.18
- Rebase on newer git tree the has a number of merges into it.
- Adjust spec file to allow direct use of git patches
- Fix to eliminate unused varables.
- Proper delete for array.

* Thu Jun 28 2012 William Cohen <wcohen@redhat.com> - 7.99-0.17
- Rebase on newer git repo.

* Thu Jun 28 2012 William Cohen <wcohen@redhat.com> - 7.99-0.16
- Eliminate dynptr.h file use with rebase on newer git repo.

* Mon Jun 25 2012 William Cohen <wcohen@redhat.com> - 7.99-0.14
- Rebase on newer git repo.

* Tue Jun 19 2012 William Cohen <wcohen@redhat.com> - 7.99-0.12
- Fix static library and header file permissions.
- Use sources from the dyninst git repositories.
- Fix 32-bit library versioning for libdyninstAPI_RT_m32.so.

* Wed Jun 13 2012 William Cohen <wcohen@redhat.com> - 7.99-0.11
- Fix library versioning.
- Move .so links to dyninst-devel.
- Remove unneded clean section.

* Fri May 11 2012 William Cohen <wcohen@redhat.com> - 7.0.1-0.9
- Clean up Makefile rules.

* Sat May 5 2012 William Cohen <wcohen@redhat.com> - 7.0.1-0.8
- Clean up spec file.

* Wed May 2 2012 William Cohen <wcohen@redhat.com> - 7.0.1-0.7
- Use "make install" and do staged build.
- Use rpm configure macro.

* Thu Mar 15 2012 William Cohen <wcohen@redhat.com> - 7.0.1-0.5
- Nuke the bundled boost files and use the boost-devel rpm instead.

* Mon Mar 12 2012 William Cohen <wcohen@redhat.com> - 7.0.1-0.4
- Initial submission of dyninst spec file.
