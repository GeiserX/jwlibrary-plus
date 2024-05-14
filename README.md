![img](https://github.com/GeiserX/jwlibrary-plus/blob/main/extra/logo.jpg?raw=true)
# JW Library Plus

[![jwlibrary-plus compliant](https://img.shields.io/github/license/GeiserX/jwlibrary-plus)](https://github.com/GeiserX/jwlibrary-plus/blob/main/LICENSE)

This project is a Telegram bot assistant to help you prepare for Jehovah's Witnesses weekend meetings. It uses ChatGPT-4o to write contextual notes for each paragraph, with configurable inputs.

## Table of Contents

- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Maintainers](#maintainers)
- [Contributing](#contributing)

## Background

JW Library Plus was conceived with the idea of facilitating the access to the Library's corpus, with the aim of bringing contextual data from Jehovah's Witness publications to enhance meeting preparation.

## Install

This project uses a [Docker container](https://hub.docker.com/repository/docker/drumsergio/jwlibrary-plu) to deploy a Telegram Bot handler.

```sh
$ docker run --name jwlibrary-plus -e TOKEN=[TOKEN] -e OPENAI_API_KEY=[KEY] drumsergio/jwlibrary-plus
```

You will need to initialize the DB with the SQL queries from `extra/create_maindb.sql`

Docker Hub image available at [drumsergio/jwlibrary-plus](https://hub.docker.com/repository/docker/drumsergio/jwlibrary-plus).

## Usage

Officially available at [@jwlibrary_plus_bot](https://t.me/jwlibrary_plus_bot).

## Maintainers

[@GeiserX](https://github.com/GeiserX).

## Contributing

Feel free to dive in! [Open an issue](https://github.com/GeiserX/jwlibrary-plus/issues/new) or submit PRs.

JW Library Plus follows the [Contributor Covenant](http://contributor-covenant.org/version/2/1/) Code of Conduct.

### Contributors

This project exists thanks to all the people who contribute. 
<a href="https://github.com/GeiserX/jwlibrary-plus/graphs/contributors"><img src="https://opencollective.com/jwlibrary-plus/contributors.svg?width=890&button=false" /></a>


