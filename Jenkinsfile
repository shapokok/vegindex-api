pipeline {
    agent any

    triggers {
        pollSCM('H/2 * * * *')
    }

    options {
        timestamps()
        buildDiscarder(logRotator(numToKeepStr: '20'))
        disableConcurrentBuilds()
        skipDefaultCheckout()
    }

    environment {
        IMAGE          = 'shapok/vegindex-api'
        TEST_IMAGE     = "${IMAGE}:test-${BUILD_NUMBER}"
        TEST_CONTAINER = "vegindex-test-${BUILD_NUMBER}"
        SMOKE          = "vegindex-smoke-${BUILD_NUMBER}"
    }

    stages {
        stage('Checkout') {
            steps {
                script {
                    def scmVars = checkout scm
                    env.GIT_BRANCH = scmVars.GIT_BRANCH
                    env.SHORT_SHA = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                }
                echo "Branch ${env.GIT_BRANCH}, commit ${env.SHORT_SHA}"
            }
        }

        stage('Lint & Unit tests') {
            steps {
                // ruff + pytest run inside the image build; a failure fails the build.
                sh 'docker build --target test -t "$TEST_IMAGE" .'
            }
        }

        stage('Publish test report') {
            steps {
                // The daemon is the host's, so a bind mount would point at the host
                // filesystem; copy the report out of a stopped container instead.
                sh '''
                    mkdir -p reports
                    docker create --name "$TEST_CONTAINER" "$TEST_IMAGE"
                    docker cp "$TEST_CONTAINER:/reports/junit.xml" reports/junit.xml
                    docker rm "$TEST_CONTAINER"
                '''
            }
        }

        stage('Build image') {
            steps {
                sh '''
                    docker build \
                        --build-arg GIT_COMMIT="$SHORT_SHA" \
                        -t "$IMAGE:$BUILD_NUMBER" \
                        -t "$IMAGE:$SHORT_SHA" \
                        -t "$IMAGE:latest" \
                        .
                '''
            }
        }

        stage('Smoke test') {
            steps {
                // Requests go through `docker exec`, so no host port is needed and
                // parallel jobs cannot clash on 8000.
                sh '''
                    docker run -d --name "$SMOKE" "$IMAGE:$BUILD_NUMBER"

                    for i in $(seq 1 30); do
                        if docker exec "$SMOKE" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" 2>/dev/null; then
                            echo "/health OK after $i attempt(s)"
                            break
                        fi
                        if [ "$i" -eq 30 ]; then
                            echo "API did not become healthy"
                            docker logs "$SMOKE"
                            exit 1
                        fi
                        sleep 2
                    done

                    docker exec "$SMOKE" python -c "
import json, sys, urllib.request
version = json.load(urllib.request.urlopen('http://127.0.0.1:8000/version', timeout=2))
print(version)
sys.exit(0 if version['commit'] == '$SHORT_SHA' else 'commit mismatch, expected $SHORT_SHA')
"
                    docker rm -f "$SMOKE"
                '''
            }
        }

        stage('Push to Docker Hub') {
            when {
                expression { env.GIT_BRANCH == 'origin/main' || env.GIT_BRANCH == 'main' }
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DOCKERHUB_USER',
                                                  passwordVariable: 'DOCKERHUB_TOKEN')]) {
                    sh '''
                        echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_USER" --password-stdin
                        docker push "$IMAGE:$BUILD_NUMBER"
                        docker push "$IMAGE:$SHORT_SHA"
                        docker push "$IMAGE:latest"
                    '''
                }
            }
        }
    }

    post {
        always {
            junit testResults: 'reports/junit.xml', allowEmptyResults: true
            sh '''
                docker logout || true
                docker rm -f "$SMOKE" "$TEST_CONTAINER" >/dev/null 2>&1 || true
                # Keep only :latest locally; drop per-build tags so images do not pile up.
                docker rmi "$TEST_IMAGE" "$IMAGE:$BUILD_NUMBER" "$IMAGE:$SHORT_SHA" >/dev/null 2>&1 || true
            '''
            deleteDir()
        }
        success {
            echo "SUCCESS: ${env.IMAGE}:${env.BUILD_NUMBER} (${env.SHORT_SHA}) built and verified"
        }
        failure {
            echo "FAILURE: build #${env.BUILD_NUMBER} failed, see the stage logs above"
        }
    }
}
