<div style="text-align: center;">
<a href="https://beam.entitle.io">
    <img width="800" src="https://entitle-public.s3.amazonaws.com/beam.svg" alt="Beam Logo">
</a>
</div>

# Beam: Securely Connect to Your Infrastructure

Beams helps you to connect easily & securely to internal AWS resources using AWS SSM Session Manager.

**Currently supported infrastructure:**
* AWS: SSM, EKS, RDS
* _GCP: Coming soon 🎉_

## Installation and initial configuration

#### Step 1: Install Beam
Start with installing beam
```shell
pip install https://github.com/entitleio/beam/releases/latest/download/beam.tar.gz
```

#### Step 2: Configure SSO
Run the following command to configure Single Sign-On (SSO):

```shell
beam configure --sso-url SSO_URL --sso-region SSO_REGION
```
Follow the Single Sign-On (SSO) and Multi-Factor Authentication (MFA) prompts until you approve.

#### Step 3: Select Accounts and Permissions
- Select the accounts you want to access.
- Choose the permission sets you require.

#### Step 4: Specify Regions and Infrastructure
- Select the regions where your infrastructure is located.
- Specify the regular expression (regex) for your bastion host.
- Choose your default Kubernetes namespace.
- Decide if you want to use Amazon Elastic Kubernetes Service (EKS) and specify the regex.
- Decide if you want to connect to Amazon Relational Database Service (RDS).

#### Step 5: Approve Configuration
Approve the configuration. This will generate a configuration file in your current user folder.

#### Step 6: Run Beam
Now you can run the following command:

```shell
sudo beam run
```
*Note: The first run will take some time as it scans your entire infrastructure.*

*Note: Beam requires sudo because it edits the hosts file.*

Congratulations! You have successfully configured your DevOps environment.

## Documentation

[Documentation] for the current version of Beam is available from the [official website].

## Contribute

Follow the [contributing guidelines](CONTRIBUTING.md) if you want to propose a change in Beam.

## Resources

* [Releases][PyPI Releases]
* [Official Website]
* [Documentation]
* [Issue Tracker]

  [PyPI]: https://pypi.org/project/beam/
  [PyPI Releases]: https://pypi.org/project/beam/#history
  [Official Website]: https://beam.entitle.io
  [Documentation]: https://beam.entitle.io/docs
  [Issue Tracker]: https://github.com/entitleio/beam/issues
  [Contributing Documentation]: CONTRIBUTING.md
